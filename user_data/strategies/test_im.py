# import indicator_opt
#
# iopt = indicator_opt.IndicatorOptHelper()
#
# # Buy hyperspace params:
# buy_params = {
#     "buy_comparison_series_1": "close",
#     "buy_comparison_series_2": "T3Average_1h",
#     "buy_operator_1": "<=",
#     "buy_operator_2": ">=",
#     "buy_series_1": "rsi",
#     "buy_series_2": "rsi_1h",
# }
#
#
# # Sell hyperspace params:
# sell_params = {
#     "sell_comparison_series_1": "sar_1h",
#     "sell_comparison_series_2": "bb_middleband_40",
#     "sell_operator_1": ">",
#     "sell_operator_2": ">=",
#     "sell_series_1": "stoch80_sma10",
#     "sell_series_2": "T3Average",
# }
# ct = indicator_opt.CombinationTester(buy_params, sell_params)
#
#
# def test_create_ct_parameters():
#     parameters = ct.create_parameters()
#     print(parameters['buy'])
#     print(parameters['sell'])
#     assert len(parameters['buy']) == 2 and len(parameters['sell']) == 1
#     ct.update_local_parameters(locals())
#     assert list(parameters['buy'].values())[0] in locals().values()
#
#
# def test_create_ioh_parameters():
#     n = 3
#     groups = iopt.create_comparison_groups('buy', n)
#     print(groups)
#     assert isinstance(groups, dict)
#     assert len(groups) == n
#     assert all([k in groups[1] for k in ['series', 'operator', 'comparison_series']])
#
