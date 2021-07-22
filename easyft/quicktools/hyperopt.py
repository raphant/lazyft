class QuickHyperopt:
    loss_func_dict = {
        '0': 'SortinoHyperOptLossDaily',
        '1': 'SortinoHyperOptLoss',
        '2': 'SharpeHyperOptLossDaily',
        '3': 'SharpeHyperOptLossDaily',
        '4': 'OnlyProfitHyperOptLoss',
        '5': 'ShortTradeDurHyperOptLoss',
    }
    spaces_dict = {
        'a': 'all',
        'b': 'buy',
        's': 'sell',
        'S': 'stoploss',
        't': 'trailing',
        'r': 'roi',
    }
    losses_help = '\n'.join([f'{k}:{v}' for k, v in loss_func_dict.items()])
    spaces_help = '\n'.join([f'{k}:{v}' for k, v in spaces_dict.items()])

    @staticmethod
    def get_loss_func(idx: str):
        return QuickHyperopt.loss_func_dict.get(idx)

    @staticmethod
    def get_spaces(space_string: str):
        for s in space_string:
            if s not in QuickHyperopt.spaces_dict:
                raise ValueError(
                    f'{s} is not a recognized spaces option in:\n'
                    f'{QuickHyperopt.spaces_help}'
                )
        return ' '.join(set([QuickHyperopt.spaces_dict.get(s) for s in space_string]))


if __name__ == '__main__':
    print(QuickHyperopt.get_spaces('sbr'))
