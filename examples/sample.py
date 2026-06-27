"""A small module with conventional (un-prefixed) names."""


class py_class_Wallet:
    def __init__(self, cents=0):
        self.cents = cents

    def py_method_deposit(self, amount):
        self.cents += amount
        return self.cents


def py_function_open_wallet(start):
    py_inst_wallet = py_class_Wallet(start)
    py_inst_wallet.py_method_deposit(100)
    return py_inst_wallet.cents
