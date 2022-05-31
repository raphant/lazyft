import re

import typer
from diskcache import Index
from lazyft import paths, strategy

app = typer.Typer()

cache = Index(str(paths.CACHE_DIR.joinpath('space_handlerify')))


@app.command()
def convert(
    strategy_name: str = typer.Argument(..., exists=True),
    save_as: str = typer.Option(None, help="New name to save modified strategy as"),
):
    # noinspection PyUnresolvedReferences
    import readline

    if '.py' not in strategy_name:
        path = paths.STRATEGY_DIR / strategy.get_file_name(strategy_name)
    else:
        path = paths.STRATEGY_DIR / strategy_name

    if not path.exists():
        raise FileNotFoundError(f"Strategy file {strategy_name} not found")
    text = path.read_text()
    # print(text)

    """
    Create a regex pattern to capture something like the following:
    base_nb_candles_buy = IntParameter(
        5, 80, default=buy_params['base_nb_candles_buy'], space='buy', optimize=True
    )
    low_offset = DecimalParameter(
        0.9, 0.99, default=buy_params['low_offset'], space='buy', optimize=True
    )
    """
    class_pattern = re.compile(r'class [\w_]+\(IStrategy\):')
    class_pattern2 = re.compile(r'class ([\w_]+)\(IStrategy\):')
    # Append "sh" to the end of class name
    class_name = class_pattern2.search(text).group(1)
    text = text.replace(class_name, class_name + 'Sh')
    # get the line number that the class is defined on
    class_line_number = [i for i, line in enumerate(text.splitlines()) if class_pattern.match(line)]
    class_line_no = class_line_number[0]
    to_insert_line = class_line_no + 1
    sh_insert = '    sh = SpaceHandler(__file__, disable=__name__ != __qualname__)'
    import_insert = 'from lazyft.space_handler import SpaceHandler'
    split_text = text.splitlines()
    split_text.insert(to_insert_line, sh_insert)
    # insert import
    split_text.insert(0, import_insert)

    text = '\n'.join(split_text)
    pattern = re.compile(
        r"(\s*[\w_]+\s*=\s*\w+Parameter\(\s*[\w,\s=\-\[\]'.]+optimize=\w+[\w,\s=\-\[\]'.]*\s*\))"
    )
    inner_pattern = re.compile(
        r"(\s*[\w_]+)\s*=\s*\w+Parameter\(\s*[\w,\s=\-\[\]'.]+optimize=\w+[\w,\s=\-\[\]'.]*\s*\)"
    )
    find = pattern.findall(text)
    assert any(find), f"No parameters found"
    # find count of regex: optimize=\w+
    count = len(re.compile(r'optimize=\w+').findall(text))
    assert count == len(find), f'{count} parameters found, but expected {len(find)} parameters'
    print(f'Found {count} parameters')
    # new_group = ''
    group = ''
    add_to_cache = True
    groups = []
    for idx, f in enumerate(find, start=1):
        cached_group = ''

        # replace optimize = True with optimize = False with regex
        inner_find = inner_pattern.findall(f)[0].strip()
        if inner_find in cache:
            group = cache[inner_find]
            add_to_cache = False
        new_group = typer.prompt(
            f"({idx}/{len(find)}) What group should {inner_find} be in?: ",
            default=group,
            show_default=True,
        )
        if add_to_cache or new_group != group:
            cache[inner_find] = new_group
            add_to_cache = True
        group = new_group
        # print('Before:', f)
        sub = re.sub(r"optimize=\w+", f"optimize=sh.get_space('{new_group}')", f)
        print(sub.strip())
        text = re.sub(
            f"{inner_find}\s*=\s*\w+Parameter\(\s*[\w,\s=\-\[\]'.]+optimize=\w+[\w,\s=\-\[\]'.]*\s*\)",
            sub.strip(),
            text,
        )
        groups.append(new_group)
    new_file = path.with_name(save_as or f'{path.stem}_sh.py')
    new_file.write_text(text)
    print(f'Added groups: {set(groups)}')
    print(f'Saved to {new_file}')
