"""In-game clock, day/night, and seasons."""
from .settings import (SECONDS_PER_STEP, DAY_START_MIN, DAY_END_MIN,
                       DAYS_PER_SEASON, SEASONS)


class TimeSystem:
    def __init__(self):
        self.minutes = DAY_START_MIN     # minutes since midnight
        self.day = 1                     # 1..28
        self.season_idx = 0
        self.year = 1
        self._acc = 0.0
        self.new_day_flag = False        # set True for one frame on day rollover

    @property
    def season(self):
        return SEASONS[self.season_idx]

    def update(self, dt):
        self.new_day_flag = False
        self._acc += dt
        while self._acc >= SECONDS_PER_STEP:
            self._acc -= SECONDS_PER_STEP
            self.minutes += 10
            if self.minutes >= DAY_END_MIN:
                self.sleep()             # auto pass out at 2am

    def sleep(self):
        """Advance to 06:00 next day; returns True so caller can run day-change logic."""
        self.minutes = DAY_START_MIN
        self.day += 1
        if self.day > DAYS_PER_SEASON:
            self.day = 1
            self.season_idx = (self.season_idx + 1) % len(SEASONS)
            if self.season_idx == 0:
                self.year += 1
        self.new_day_flag = True

    def clock_str(self):
        # int() guards the :02d format below -- minutes is an int in normal
        # play, but a float (e.g. from an edited/modded save) must never be
        # able to crash the HUD draw.
        mins = int(self.minutes)
        h = (mins // 60) % 24
        m = mins % 60
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{m:02d} {suffix}"

    def date_str(self):
        return f"{self.season} {self.day}  (Y{self.year})"

    def darkness(self):
        """0.0 (full day) .. ~0.6 (deep night) overlay alpha factor."""
        m = self.minutes
        if m < 18 * 60:          # before 18:00 -> full day
            return 0.0
        if m >= 24 * 60:
            return 0.6
        # dusk 18:00 -> 24:00
        t = (m - 18 * 60) / (6 * 60)
        return min(0.6, t * 0.6)
