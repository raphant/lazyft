#!/usr/bin/env bash
mkdir buildfiles
# clear buildfiles
rm -rf buildfiles/*
# create a list of lazyft_pkg, indicatormix, lft_rest, coin_based_strategy
list_of_packages=(lazyft_pkg indicatormix lft_rest coin_based_strategy)
# for each package in list_of_packages, do: cd lazyft_pkg && python setup.py bdist_wheel && mv dist/* ../buildfiles && cd ..
for package in "${list_of_packages[@]}"
do
    cd "$package" && python setup.py bdist_wheel && mv dist/* ../buildfiles && rm -rf dist build "$package".egg* && cd ..
done
# add WHL files to buildfiles/requirements.txt
cd buildfiles
ls -1 | grep -v requirements.txt > requirements.txt

