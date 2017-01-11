#!/usr/bin/python3
import asyncio
import curses
import decimal
import traceback

import api

COLOR_DARKBLACK = 32
COLOR_SUPERWHITE = 33

PAIR_ACTIVE_TAB = 1
PAIR_INACTIVE_TAB = 2
PAIR_TABBAR_BG = 3
PAIR_ACTIVE_ACCOUNT_SEL = 4
PAIR_INACTIVE_ACCOUNT_SEL = 5
PAIR_POSITIVE_VALUE = 6
PAIR_NEGATIVE_VALUE = 7

class Application:

    def __init__(self, screen, ws):
        self.screen = screen
        self._ws = ws

    def _active_tab_color(self):
        return curses.color_pair(PAIR_ACTIVE_TAB) | curses.A_BOLD

    def _inactive_tab_color(self):
        return curses.color_pair(PAIR_INACTIVE_TAB) | curses.A_UNDERLINE

    def _draw_tab_bar(self):
        for x in range(0, self.screen.getmaxyx()[1]):
            self.screen.addch(0, x, " ", curses.color_pair(PAIR_TABBAR_BG))
        tab_width = 8
        for i, tab in enumerate(self._account_names):
            x = i * tab_width
            tab_string = " %s " % tab[:tab_width - 2]
            tab_string += " " * (tab_width - len(tab_string))
            if i == self._current_tab:
                color = self._active_tab_color()
            else:
                color = self._inactive_tab_color()
            self.screen.addstr(0, x, tab_string, color)

    async def _display_balance(self):
        ec, balance = await api.Wallet.balance(self._ws, self._active_pocket)
        self.screen.addstr(2, 2, "Balance: %s BTC" % balance)

    async def _display_pockets(self):
        ec, self._pockets = await api.Pocket.list(self._ws)
        self.screen.addstr(4, 2, "Pockets:")
        if self._current_pocket == 0:
            color = self._active_account_color()
        else:
            color = self._inactive_account_color()
        self._active_pocket = None
        self.screen.addstr(5, 4, "All", color)
        for i, pocket in enumerate(self._pockets):
            if i + 1 == self._current_pocket:
                color = self._active_account_color()
                self._active_pocket = pocket
            else:
                color = self._inactive_account_color()
            self.screen.addstr(6 + i, 4, pocket, color)

        end_item = len(self._pockets) + 1
        if self._current_pocket == end_item:
            color = self._active_account_color()
        else:
            color = self._inactive_account_color()
        self.screen.addstr(6 + end_item, 4, "New pocket", color)

    async def _display_stealth_addr(self):
        ec, stealth = await api.Wallet.stealth(self._ws, self._active_pocket)
        off = 7 + len(self._pockets) + 2
        self.screen.addstr(off, 2, "Stealth address:")
        self.screen.addstr(off + 1, 4, stealth)

    async def _display_receive_addrs(self):
        ec, addrs = await api.Wallet.receive(self._ws, self._active_pocket)
        off = 7 + len(self._pockets) + 5
        self.screen.addstr(off, 2, "Addresses:")
        for i, addr in enumerate(addrs):
            y = off + 1 + i
            maxy = self.screen.getmaxyx()[0] - 2
            if y == maxy:
                self.screen.addstr(y, 4, "...")
                break
            else:
                self.screen.addstr(y, 4, addr)

    def _display_status(self):
        maxy = self.screen.getmaxyx()[0] - 1
        self.screen.addstr(maxy, 0, self._status)
        self._status = ""

    async def display_main_window(self):
        self.screen.clear()

        self._draw_tab_bar()

        await self._display_pockets()

        await self._display_balance()

        await self._display_stealth_addr()

        await self._display_receive_addrs()

        self._display_status()

        self.screen.refresh()

    async def start(self):
        self._status = ""
        self._active_account = None
        self._active_pocket = None

        while True:
            self._active_account, self._account_names = \
                await api.Account.list(self._ws)

            if self._active_account is not None:
                break

            await self._select_account()

        self._current_tab = self._account_names.index(self._active_account)
        self._current_pocket = 0
        while True:
            await self.display_main_window()
            c = self.screen.getch()
            if c == curses.KEY_RIGHT and len(self._account_names) > 1:
                self._current_tab += 1
                if self._current_tab >= len(self._account_names):
                    self._current_tab = 0
                await self._activate_account()
            elif c == curses.KEY_LEFT and len(self._account_names) > 1:
                self._current_tab -= 1
                if self._current_tab < 0:
                    self._current_tab = len(self._account_names) - 1
                await self._activate_account()
            elif c == curses.KEY_DOWN:
                self._current_pocket += 1
                if self._current_pocket > len(self._pockets) + 1:
                    self._current_pocket = 0
            elif c == curses.KEY_UP:
                self._current_pocket -= 1
                if self._current_pocket < 0:
                    self._current_pocket = len(self._pockets) + 1
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                if self._current_pocket == len(self._pockets) + 1:
                    await self._create_pocket()
                else:
                    await self._send_screen()

    async def _send_screen(self):
        ec, self._history = await api.Wallet.history(self._ws,
                                                     self._active_pocket)
        self._send_fields = ["", "", "", ""]
        self._selected_send_item = 0
        while True:
            self._display_history()
            c = self.screen.getch()
            if c == curses.KEY_UP:
                self._selected_send_item -= 1
                if self._selected_send_item < 0:
                    self._selected_send_item = 3
            elif c == curses.KEY_DOWN:
                self._selected_send_item += 1
                if self._selected_send_item > 3:
                    self._selected_send_item = 0
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                if self._selected_send_item == 0:
                    break
                _, addr, amount, fee = self._send_fields
                try:
                    decimal.Decimal(amount)
                except decimal.InvalidOperation:
                    self._status = "Invalid amount"
                    break
                try:
                    decimal.Decimal(fee)
                except decimal.InvalidOperation:
                    self._status = "Invalid fee"
                    break
                addr_type = await api.Daemon.validate_address(self._ws,
                                                              addr)
                if addr_type == "invalid":
                    self._status = "Invalid address"
                    break
                dests = [(addr, amount)]
                ec, tx_hash = await api.Wallet.send(self._ws, dests, fee=fee,
                                                    pocket=self._active_pocket)
                if ec:
                    self._status = ec.name
                else:
                    self._status = "Sent %s" % tx_hash
                break
            elif c == curses.KEY_BACKSPACE:
                self._send_fields[self._selected_send_item] = \
                        self._send_fields[self._selected_send_item][:-1]
            elif c == curses.KEY_LEFT or c == curses.KEY_RIGHT:
                pass
            else:
                self._send_fields[self._selected_send_item] += chr(c)

    def _display_history(self):
        self.screen.clear()

        self._draw_tab_bar()


        for i in range(4):
            if i == self._selected_send_item:
                color = self._active_account_color()
            else:
                color = self._inactive_account_color()

            row_len = 32
            if i == 0:
                self.screen.addstr(2, 2, "< Return back", color)
            elif i == 1:
                row_len = 118
                self.screen.addstr(4, 2, "Address:")
            elif i == 2:
                self.screen.addstr(6, 2, "Amount:")
            elif i == 3:
                self.screen.addstr(8, 2, "Fee:")

            if row_len >= self.screen.getmaxyx()[1] - 2:
                row_len = self.screen.getmaxyx()[1] - 2

            value = self._send_fields[i]
            row_string = value + "_" * (row_len - len(value))
            if i != 0:
                self.screen.addstr(3 + i * 2, 2, row_string, color)

        history_items = []
        for row in self._history:
            if row["type"] == "output":
                height = row["output"]["height"]
            else:
                height = row["spend"]["height"]
            history_items.append((row["addr"], row["value"], height))
        get_height = lambda item: item[2]
        history_items.sort(key=get_height, reverse=True)

        for i, row in enumerate(history_items):
            addr, value, height = row
            value = decimal.Decimal(value) / 10**8
            if value >= 0:
                color = curses.color_pair(PAIR_POSITIVE_VALUE)
            else:
                color = curses.color_pair(PAIR_NEGATIVE_VALUE)
            maxy = self.screen.getmaxyx()[0] - 2
            y = 11 + i
            if y == maxy:
                self.screen.addstr(y, 2, "...")
                break
            self.screen.addstr(y, 2, addr)
            self.screen.addstr(y, 40, str(value), color)

    async def _create_pocket(self):
        pocket_name = ""
        while True:
            self.screen.clear()

            self._draw_tab_bar()

            self.screen.addstr(2, 2, "Pocket name:")

            self.screen.addstr(4, 4, pocket_name)

            c = self.screen.getch()
            if c == 27:
                self._status = "Cancelled"
                break
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                ec = await api.Pocket.create(self._ws, pocket_name)
                if ec:
                    self._status = ec.name
                else:
                    self._status = "Created"
                break
            elif c == curses.KEY_BACKSPACE:
                pocket_name = pocket_name[:-1]
            elif c == curses.KEY_LEFT or c == curses.KEY_RIGHT:
                pass
            else:
                pocket_name += chr(c)

    async def _activate_account(self):
        self._active_pocket = None
        password = await self._enter_password_tab2()
        if password is None:
            return
        self.screen.clear()
        self._draw_tab_bar()
        account_name = self._account_names[self._current_tab]
        ec = await api.Account.set(self._ws, account_name, password)
        if ec:
            self.screen.addstr(10, 2, "Error: %s" % ec.name)
        else:
            return

    async def _enter_password_tab2(self):
        password = ""
        while True:
            self.screen.clear()
            self._draw_tab_bar()
            self.screen.addstr(2, 2, "Password:")
            self.screen.addstr(4, 2, "*" * len(password))
            c = self.screen.getch()
            if c == curses.KEY_BACKSPACE:
                password = password[:-1]
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                return password
            elif c == curses.KEY_LEFT:
                self._current_tab -= 1
                if self._current_tab < 0:
                    self._current_tab = len(self._account_names) - 1
                await self._activate_account()
                return None
            elif c == curses.KEY_RIGHT:
                self._current_tab += 1
                if self._current_tab >= len(self._account_names):
                    self._current_tab = 0
                await self._activate_account()
                return None
            else:
                password += chr(c)

    def _active_account_color(self):
        return curses.color_pair(PAIR_ACTIVE_ACCOUNT_SEL)
    def _inactive_account_color(self):
        return curses.color_pair(PAIR_INACTIVE_ACCOUNT_SEL)

    async def _select_account(self):
        row_len = 20
        selected = 0
        while True:
            self.screen.clear()
            self.screen.addstr(1, 2, "Select an account:")
            rows = self._account_names + ["New account"]
            for i, account in enumerate(rows):
                row_string = "  %s" % account
                row_string += " " * (row_len - len(row_string))
                if i == selected:
                    color = self._active_account_color()
                else:
                    color = self._inactive_account_color()
                self.screen.addstr(i + 3, 2, row_string, color)
            self._display_status()
            self.screen.refresh()
            c = self.screen.getch()
            if c == curses.KEY_UP:
                selected -= 1
                if selected < 0:
                    selected = len(rows) - 1
            elif c == curses.KEY_DOWN:
                selected += 1
                if selected >= len(rows):
                    selected = 0
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                if selected == len(rows) - 1:
                    await self._new_account()
                    break
                else:
                    account_name = rows[selected]
                    password = self._enter_password()
                    ec = await api.Account.set(self._ws, account_name, password)
                    if ec:
                        self.screen.addstr(10, 2, "Error: %s" % ec.name)
                    else:
                        return

    async def _new_account(self):
        index = 0
        account_name = ""
        password = ""
        is_testnet = False
        while True:
            self.screen.clear()
            self.screen.addstr(1, 2, "Account name:")
            if index == 0:
                color = self._active_account_color()
            else:
                color = self._inactive_account_color()
            row_len = 26
            acc_row = account_name + "_" * (row_len - len(account_name))
            self.screen.addstr(2, 2, acc_row, color)
            self.screen.addstr(3, 2, "Password:")
            if index == 1:
                color = self._active_account_color()
            else:
                color = self._inactive_account_color()
            pass_row = "*" * len(password) + "_" * (row_len - len(password))
            self.screen.addstr(4, 2, pass_row, color)
            if index == 2:
                color = self._active_account_color()
            else:
                color = self._inactive_account_color()
            mark = "X" if is_testnet else " "
            self.screen.addstr(6, 2, "[%s] Testnet" % mark, color)
            c = self.screen.getch()
            if c == curses.KEY_BACKSPACE:
                if index == 0:
                    account_name = account_name[:-1]
                elif index == 1:
                    password = password[:-1]
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                ec = await api.Account.create(self._ws, account_name,
                                              password, is_testnet)
                if ec:
                    self._status = ec.name
                break
            elif c == curses.KEY_UP:
                index -= 1
                if index < 0:
                    index = 2
            elif c == curses.KEY_DOWN:
                index += 1
                if index >= 3:
                    index = 0
            elif c == ord(" ") and index == 2:
                is_testnet = not is_testnet
            else:
                if index == 0:
                    account_name += chr(c)
                elif index == 1:
                    password += chr(c)

    def _enter_password(self):
        password = ""
        while True:
            self.screen.clear()
            self.screen.addstr(1, 2, "Enter a password:")
            self.screen.addstr(3, 2, "*" * len(password))
            c = self.screen.getch()
            if c == curses.KEY_BACKSPACE:
                password = password[:-1]
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                return password
            else:
                password += chr(c)

async def main():
    screen = curses.initscr()
    try:
        await start(screen)
    except KeyboardInterrupt:
        finish(screen)
    except:
        finish(screen)
        traceback.print_exc()
    else:
        finish(screen)

def finish(screen):
    curses.nocbreak()
    screen.keypad(False)
    curses.echo()
    curses.endwin()

async def start(screen):
    curses.noecho()
    curses.cbreak()
    screen.keypad(True)
    curses.start_color()

    curses.use_default_colors()
    curses.curs_set(0)

    if curses.can_change_color():
        curses.init_color(COLOR_DARKBLACK, 0, 0, 0)
        curses.init_color(COLOR_SUPERWHITE, 1000, 1000, 1000)

        curses.init_pair(PAIR_ACTIVE_TAB, COLOR_SUPERWHITE, COLOR_DARKBLACK)
        curses.init_pair(PAIR_TABBAR_BG, COLOR_DARKBLACK, COLOR_SUPERWHITE)
    else:
        curses.init_pair(PAIR_ACTIVE_TAB,
                         curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(PAIR_TABBAR_BG,
                         curses.COLOR_BLACK, curses.COLOR_WHITE)

    curses.init_pair(PAIR_INACTIVE_TAB,
                     curses.COLOR_WHITE, curses.COLOR_BLACK)

    curses.init_pair(PAIR_ACTIVE_ACCOUNT_SEL,
                     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(PAIR_INACTIVE_ACCOUNT_SEL, curses.COLOR_WHITE, -1)

    curses.init_pair(PAIR_POSITIVE_VALUE, curses.COLOR_GREEN, -1)
    curses.init_pair(PAIR_NEGATIVE_VALUE, curses.COLOR_RED, -1)

    websockets_path = "ws://localhost:8888"
    async with api.WebSocket(websockets_path) as ws:
        app = Application(screen, ws)
        await app.start()

asyncio.get_event_loop().run_until_complete(main())

