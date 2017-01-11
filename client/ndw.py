import asyncio
import curses
import traceback

import api

COLOR_DARKBLACK = 32
COLOR_SUPERWHITE = 33

PAIR_ACTIVE_TAB = 1
PAIR_INACTIVE_TAB = 2
PAIR_TABBAR_BG = 3
PAIR_ACTIVE_ACCOUNT_SEL = 4
PAIR_INACTIVE_ACCOUNT_SEL = 5

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
        ec, balance = await api.Wallet.balance(self._ws)
        self.screen.addstr(3, 2, "Balance: %s BTC" % balance)

    async def _display_pockets(self):
        ec, pockets = await api.Pocket.list(self._ws)
        self.screen.addstr(5, 2, "Pockets:")
        for i, pocket in enumerate(pockets):
            self.screen.addstr(6 + i, 4, pocket)

    async def display_main_window(self):
        self.screen.clear()

        self._draw_tab_bar()

        await self._display_balance()

        await self._display_pockets()

        self.screen.refresh()

    async def start(self):
        self._active_account = None

        while True:
            self._active_account, self._account_names = \
                await api.Account.list(self._ws)

            if self._active_account is not None:
                break

            await self._select_account()

        self._current_tab = self._account_names.index(self._active_account)
        while True:
            await self.display_main_window()
            c = self.screen.getch()
            if c == curses.KEY_RIGHT:
                self._current_tab += 1
                if self._current_tab >= len(self._account_names):
                    self._current_tab = 0
                await self._activate_account()
            elif c == curses.KEY_LEFT:
                self._current_tab -= 1
                if self._current_tab < 0:
                    self._current_tab = len(self._account_names) - 1
                await self._activate_account()

    async def _activate_account(self):
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
        self.screen.addstr(1, 2, "Select an account:")
        row_len = 20
        selected = 0
        while True:
            rows = self._account_names + ["New account"]
            for i, account in enumerate(rows):
                row_string = "  %s" % account
                row_string += " " * (row_len - len(row_string))
                if i == selected:
                    color = self._active_account_color()
                else:
                    color = self._inactive_account_color()
                self.screen.addstr(i + 3, 2, row_string, color)
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
                    pass
                else:
                    account_name = rows[selected]
                    password = self._enter_password()
                    ec = await api.Account.set(self._ws, account_name, password)
                    if ec:
                        self.screen.addstr(10, 2, "Error: %s" % ec.name)
                    else:
                        return

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
    curses.init_pair(PAIR_INACTIVE_TAB, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(PAIR_TABBAR_BG, COLOR_DARKBLACK, COLOR_SUPERWHITE)
    curses.init_pair(PAIR_ACTIVE_ACCOUNT_SEL,
                     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(PAIR_INACTIVE_ACCOUNT_SEL, curses.COLOR_WHITE, -1)

    websockets_path = "ws://localhost:8888"
    async with api.WebSocket(websockets_path) as ws:
        app = Application(screen, ws)
        await app.start()

asyncio.get_event_loop().run_until_complete(main())

