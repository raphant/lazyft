"""
Create a gui that displays data.
The gui has two widgets, a Text and a ComboBox.
The Combobox calls a function called "on_change" that updates the label with the value of ComboBox, when changed.
Uses tkinter.
"""

import tkinter as tk
from threading import Thread
from tkinter.ttk import Combobox

import dotenv
from dotenv import load_dotenv
from freqtrade.data.dataprovider import DataProvider
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

dotenv.load_dotenv('.custom_env')


class DataView(object):
    def __init__(self, parent, strategy: IStrategy):
        self.root = parent
        self.strategy = strategy
        self.root.title("MyApp")
        self.frame = tk.Frame(parent)
        self.frame.pack()

        self.label = tk.Label(self.frame, text="")
        self.label.pack()

        self.combo = Combobox(self.frame, values=strategy.dp.current_whitelist())
        self.combo.pack()
        self.combo.bind("<<ComboboxSelected>>", self.on_change)

        self.num_buys = tk.Label(
            self.frame, text='Click "Get Trades" to get current trades'
        )
        self.num_buys.pack()

        self.button = tk.Button(
            self.frame, text="Get Trades", command=self.button_clicked
        )
        self.button.pack()

    def on_change(self, event):
        df, _ = self.strategy.dp.get_analyzed_dataframe(self.combo.get(), '5m')
        self.label.config(
            text=df.tail(5)[
                ['date', 'open', 'high', 'low', 'close', 'sell_tag', 'buy_tag']
            ].to_string()
        )

    def button_clicked(self):
        """
        Change the text of the label num_buys
        """
        self.num_buys["text"] = '\n'.join([str(t) for t in Trade.get_open_trades()])

    @staticmethod
    def start_in_new_thread(strategy: IStrategy):
        def worker():
            root = tk.Tk()
            DataView(root, strategy)
            root.mainloop()

        thread = Thread(target=worker, daemon=True)
        thread.start()
        return thread


if __name__ == "__main__":
    root = tk.Tk()
    myapp = DataView(root)
    root.mainloop()
