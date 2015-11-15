"""
Launch with
PYTHONPATH=`pwd` bokeh serve numba_hsa_examples/kde_bokeh/map_patch.py
"""
from bokeh.sampledata import us_states
from bokeh.plotting import figure
from bokeh.io import curdoc
from bokeh.models import Range1d, ColumnDataSource
from bokeh.models.widgets import HBox, VBox, Select
from bokeh import palettes
import numpy as np
import itertools
from numba_hsa_examples.kde_bokeh import kde
from numba_hsa_examples.kde_bokeh import dataloader
from numba_hsa_examples.kde_bokeh import plotting


def get_us_state_outline():
    states = us_states.data.copy()

    # Remove HAWAII and Alaska
    del states["HI"]
    del states["AK"]

    # XXX: If the plot disappear after awhile, uncomment the below.
    # # These state is somehow causing error
    # bad = """
    # KY
    # RI
    # FL
    # CA
    # NY
    # """
    #
    # # Remove "bad" states
    # for c in bad.split():
    #     del states[c.strip()]

    state_xs = [states[code]["lons"] for code in states]
    state_ys = [states[code]["lats"] for code in states]

    return state_xs, state_ys


def plot_state_outline(plot, state_xs, state_ys):
    plot.patches(state_xs, state_ys, fill_alpha=0.2, line_color="#884444",
                 line_width=2)


class ViewListener(object):
    def __init__(self, plot, density_overlay, name):
        self.plot = plot
        self.density_overlay = density_overlay
        self.name = name
        self._last_view = np.array([0., 0., 0., 0., 0., 0.], dtype=np.float32)

    def __call__(self, attrname, old, new):
        left = self.plot.x_range.start
        right = self.plot.x_range.end
        bottom = self.plot.y_range.start
        top = self.plot.y_range.end

        cur_view = np.array([right - left, top - bottom,
                             left, right, bottom, top], dtype=np.float32)
        changed_percents = np.abs(cur_view - self._last_view) / cur_view

        # change in view is more than 5%
        if np.any(changed_percents > 0.05):
            # do redraw
            self.density_overlay.update(left, right, bottom, top)
            self._last_view = cur_view


def minmax(arr):
    expanded = [v for vl in arr for v in vl]
    return min(expanded), max(expanded)


class DensityOverlay(object):
    def __init__(self, left, right, bottom, top):
        self.use_hsa = bool(kde.USE_HSA)
        print("Loading data")
        if True:
            df = dataloader.load_all_data(left, right, bottom, top)
            self.lon = df.lon.values
            self.lat = df.lat.values
        else:
            self.lon = np.random.random(100) * (right - left) + left
            self.lat = np.random.random(100) * (top - bottom) + bottom

        self.source = ColumnDataSource(data=self._make_dict(left, right,
                                                            bottom, top))


    def _make_dict(self, left, right, bottom, top):
        ny = nx = 50
        x = np.linspace(left, right, nx)
        y = np.linspace(bottom, top, ny)

        xx, yy = zip(*itertools.product(x, y))

        dw = (right - left) / (nx - 1)
        dh = (top - bottom) / (ny - 1)

        print("Compute density")
        pdf = kde.compute_density(self.lon, self.lat, xx, yy,
                                  use_hsa=self.use_hsa)
        print("Done")
        cm = plotting.RGBColorMapper(0.0, 1.0, palettes.Reds9)
        cols = cm.color(1 - pdf / np.ptp(pdf))

        # cols = [random.choice(palettes.Spectral9) for _ in range(len(xx))]
        return {
            'lon': xx,
            'lat': yy,
            'width': [dw] * len(xx),
            'height': [dh] * len(yy),
            'colors': cols,
        }

    def update(self, left, right, bottom, top):
        # TODO: The re-evaluation code goes here
        dct = self._make_dict(left, right, bottom, top)
        self.source.data = dct

    def draw(self, plot):
        plot.rect(x="lon", y="lat", width="width", height="height",
                  fill_color="colors", fill_alpha=0.50, line_alpha=0.1,
                  source=self.source)
        # plot.cross(x=self.lon, y=self.lat, size=2, color='black')

    def backend_change_listener(self, attr, old, new):
        self.use_hsa = new == 'HSA'
        print("select", new)


def main():
    state_xs, state_ys = get_us_state_outline()
    left, right = minmax(state_xs)
    bottom, top = minmax(state_ys)
    plot = figure(title="US Map Lightning", plot_width=1000,
                  plot_height=700,
                  tools="pan, box_zoom, reset",
                  x_range=Range1d(left, right),
                  y_range=Range1d(bottom, top))

    plot_state_outline(plot, state_xs, state_ys)

    density_overlay = DensityOverlay(left, right, bottom, top)
    density_overlay.draw(plot)

    listener = ViewListener(plot, density_overlay, name="viewport")

    plot.x_range.on_change("start", listener)
    plot.x_range.on_change("end", listener)
    plot.y_range.on_change("start", listener)
    plot.y_range.on_change("end", listener)

    backends = ["CPU", "HSA"]
    default_value = backends[kde.USE_HSA]
    backend_select = Select(name="backend", value=default_value,
                            options=backends)
    backend_select.on_change('value', density_overlay.backend_change_listener)

    doc = curdoc()
    # XXX: Cannot use VBox/HBox?
    #      Layout is now random due to hashing
    doc.add(plot)
    doc.add(backend_select)


main()
