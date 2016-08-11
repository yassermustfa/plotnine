from __future__ import absolute_import, division, print_function

from copy import deepcopy

import numpy as np
from matplotlib.cbook import Bunch

from ..utils import suppress

# For default matplotlib backend
with suppress(ImportError):
    import matplotlib.pyplot as plt
    import matplotlib.text as mtext
    import matplotlib.patches as mpatch


class facet(object):
    """
    Base class for all facets

    Parameters
    ----------
    scales : 'fixed' | 'free' | 'free_x' | 'free_y'
        Whether ``x`` or ``y`` scales should be allowed (free)
        to vary according to the data on each of the panel.
        Default is ``'fixed'``.
    shrink : bool
        Whether to shrink the scales to the output of the
        statistics instead of the raw data. Default is ``True``.
    labeller : str | function
        How to label the facets. If it is a ``str``, it should
        be one of ``'label_value'`` ``'label_both'`` or
        ``'label_context'``. Default is ``'label_value'``
    as_table : bool
        If ``True``, the facets are laid out like a table with
        the highest values at the bottom-right. If ``False``
        the facets are laid out like a plot with the highest
        value a the top-right. Default it ``True``.
    drop : bool
        If ``True``, all factor levels not used in the data
        will automatically be dropped. If ``False``, all
        factor levels will be shown, regardless of whether
        or not they appear in the data. Default is ``True``.
    dir : 'h' | 'v'
        Direction in which to layout the panels. ``h`` for
        horizontal and ``v`` for vertical.
    """
    #: number of columns
    ncol = None
    #: number of rows
    nrow = None
    as_table = True
    drop = True
    shrink = True
    #: Which axis scales are free
    free = {'x': True, 'y': True}
    # Theme object, automatically updated before drawing the plot
    theme = None
    # Figure object on which the facet panels are created
    figure = None
    # coord object, automatically updated before drawing the plot
    coordinates = None
    # panel object, automatically updated before drawing the plot
    panel = None
    # Axes
    axs = None
    # Number of facet variables along the horizontal axis
    num_vars_x = 0
    # Number of facet variables along the vertical axis
    num_vars_y = 0

    def __init__(self, scales='fixed', shrink=True,
                 labeller='label_value', as_table=True,
                 drop=True, dir='h'):
        from .labelling import as_labeller
        self.shrink = shrink
        self.labeller = as_labeller(labeller)
        self.as_table = as_table
        self.drop = drop
        self.dir = dir
        self.free = {'x': scales in ('free_x', 'free'),
                     'y': scales in ('free_y', 'free')}

    def __radd__(self, gg, inplace=False):
        gg = gg if inplace else deepcopy(gg)
        gg.facet = self
        return gg

    def set_breaks_and_labels(self, ranges, layout_info, pidx):
        ax = self.axs[pidx]
        # Add axes and labels on all sides. The super
        # class should remove what is unnecessary

        # limits
        ax.set_xlim(ranges['x_range'])
        ax.set_ylim(ranges['y_range'])

        # breaks
        ax.set_xticks(ranges['x_major'])
        ax.set_yticks(ranges['y_major'])

        # minor breaks
        ax.set_xticks(ranges['x_minor'], minor=True)
        ax.set_yticks(ranges['y_minor'], minor=True)

        # labels
        ax.set_xticklabels(ranges['x_labels'])
        ax.set_yticklabels(ranges['y_labels'])

        get_property = self.theme.themeables.property
        # Padding between ticks and text
        try:
            margin = get_property('axis_text_x', 'margin')
        except KeyError:
            pad_x = 2.4
        else:
            pad_x = margin.get_as('t', 'pt')

        try:
            margin = get_property('axis_text_y', 'margin')
        except KeyError:
            pad_y = 2.4
        else:
            pad_y = margin.get_as('r', 'pt')

        ax.tick_params(axis='x', which='major', pad=pad_x)
        ax.tick_params(axis='y', which='major', pad=pad_y)

    def make_figure_and_axs(self, panel, theme, coordinates):
        num_panels = len(panel.layout)
        figure, axs = plt.subplots(self.nrow, self.ncol,
                                   sharex=False, sharey=False)
        axs = np.asarray(axs)
        # Dictionary to collect matplotlib objects that will
        # be targeted for theming by the themeables
        figure._themeable = {}

        # Used for labelling the x and y axes
        self.first_ax = axs.ravel()[0]
        self.last_ax = axs.ravel()[num_panels-1]

        # FIXME: The logic below does not handle the
        # rare case when as_table=False and direction='v'
        if not self.as_table:
            axs = axs[::-1]

        order = 'C' if self.dir == 'h' else 'F'
        try:
            axs = axs.ravel(order)
        except AttributeError:
            axs = [axs]

        # No panel, do not let MPL put axes
        for ax in axs[num_panels:]:
            figure.delaxes(ax)

        axs = axs[:num_panels]
        self.axs = axs
        self.panel = panel
        self.theme = theme
        self.coordinates = coordinates
        self.figure = figure
        self.theme.setup_figure(figure)
        self.spaceout_and_resize_panels()
        return figure, axs

    def spaceout_and_resize_panels(self):
        """
        Adjust the spacing between the panels and resize them
        to meet the aspect ratio
        """
        pass

    def inner_strip_margins(self, location):
        if location == 'right':
            strip_name = 'strip_text_y'
            side1, side2 = 'l', 'r'
        else:
            strip_name = 'strip_text_x'
            side1, side2 = 't', 'b'

        try:
            margin = self.theme.themeables.property(
                strip_name, 'margin')
        except:
            m1, m2 = 3, 3
        else:
            m1 = margin.get_as(side1, 'pt')
            m2 = margin.get_as(side2, 'pt')

        return m1, m2

    def strip_size(self, location='top', num_lines=None):
        """
        Breadth of the strip background in inches

        Parameters
        ----------
        location : 'top' | 'right'
            Location of the strip text
        num_lines : int
            Number of text lines
        """
        dpi = 72.27
        theme = self.theme
        get_property = theme.themeables.property

        if location == 'right':
            strip_name = 'strip_text_y'
            num_lines = num_lines or self.num_vars_y
        else:
            strip_name = 'strip_text_x'
            num_lines = num_lines or self.num_vars_x

        if not num_lines:
            return 0

        # The facet labels are placed onto the figure using
        # transAxes dimensions. The line height and line
        # width are mapped to the same [0, 1] range
        # i.e (pts) * (inches / pts) * (1 / inches)
        try:
            fontsize = get_property(strip_name, 'size')
        except KeyError:
            fontsize = float(theme.rcParams.get('font.size', 10))

        try:
            linespacing = get_property(strip_name, 'linespacing')
        except KeyError:
            linespacing = 1

        # margins on either side of the strip text
        m1, m2 = self.inner_strip_margins(location)
        # Using figure.dpi value here does not workout well!
        breadth = (linespacing*fontsize) * num_lines / dpi
        breadth = breadth + (m1 + m2) / dpi
        return breadth

    def strip_text_position(self, location, strip_size, pid):
        dpi = 72.27
        t, b, l, r = self.strip_background_limits(location, pid)
        m1, m2 = self.inner_strip_margins(location)
        m1, m2 = m1/dpi, m2/dpi

        if location == 'top':
            t = b + strip_size
            x = (l + r)/2
            y = (b + t + m1 - m2)/2
        else:
            r = l + strip_size
            x = (l + r - m1 + m2)/2
            y = (t + b)/2

        return x, y

    def strip_dimensions(self, text_lines, location, pid):
        """
        Calculate the dimension

        Returns
        -------
        out : Bunch
            A structure with all the coordinates required
            to draw the strip text and the background box.
        """
        dpi = 72.27
        num_lines = len(text_lines)
        get_property = self.theme.themeables.property
        ax = self.axs[pid]
        bbox = ax.get_window_extent().transformed(
            self.figure.dpi_scale_trans.inverted())
        ax_width, ax_height = bbox.width, bbox.height  # in inches
        strip_size = self.strip_size(location, num_lines)
        m1, m2 = self.inner_strip_margins(location)
        m1, m2 = m1/dpi, m2/dpi
        margin = 0  # default

        if location == 'right':
            box_x = 1
            box_y = 0
            box_width = strip_size/ax_width
            box_height = 1
            # y & height properties of the background slide and
            # shrink the strip vertically. The y margin slides
            # it horizontally.
            with suppress(KeyError):
                box_y = get_property('strip_background_y', 'y')
            with suppress(KeyError):
                box_height = get_property('strip_background_y', 'height')
            with suppress(KeyError):
                margin = get_property('strip_margin_y')
            x = 1 + (strip_size-m2+m1) / (2*ax_width)
            y = (2*box_y+box_height)/2
            # margin adjustment
            hslide = 1 + margin*strip_size/ax_width
            x *= hslide
            box_x *= hslide
        else:
            box_x = 0
            box_y = 1
            box_width = 1
            box_height = strip_size/ax_height
            # x & width properties of the background slide and
            # shrink the strip horizontally. The y margin slides
            # it vertically.
            with suppress(KeyError):
                box_x = get_property('strip_background_x', 'x')
            with suppress(KeyError):
                box_width = get_property('strip_background_x', 'width')
            with suppress(KeyError):
                margin = get_property('strip_margin_x')
            x = (2*box_x+box_width)/2
            y = 1 + (strip_size-m1+m2)/(2*ax_height)
            # margin adjustment
            vslide = 1 + margin*strip_size/ax_height
            y *= vslide
            box_y *= vslide

        dimensions = Bunch(x=x, y=y, box_x=box_x, box_y=box_y,
                           box_width=box_width,
                           box_height=box_height)
        return dimensions

    def draw_strip_text(self, text_lines, location, pid):
        """
        Create a background patch and put a label on it
        """
        ax = self.axs[pid]
        themeable = self.figure._themeable
        dim = self.strip_dimensions(text_lines, location, pid)

        if location == 'right':
            rotation = -90
            label = '\n'.join(reversed(text_lines))
        else:
            rotation = 0
            label = '\n'.join(text_lines)

        rect = mpatch.FancyBboxPatch((dim.box_x, dim.box_y),
                                     width=dim.box_width,
                                     height=dim.box_height,
                                     facecolor='lightgrey',
                                     edgecolor='None',
                                     transform=ax.transAxes,
                                     zorder=2.2,  # > ax line & boundary
                                     boxstyle='square, pad=0',
                                     clip_on=False)

        text = mtext.Text(dim.x, dim.y, label,
                          rotation=rotation,
                          verticalalignment='center',
                          horizontalalignment='center',
                          transform=ax.transAxes,
                          zorder=3.3,  # > rect
                          clip_on=False)

        ax.add_artist(rect)
        ax.add_artist(text)

        for key in ('strip_text_x', 'strip_text_y',
                    'strip_background_x', 'strip_background_y'):
            if key not in themeable:
                themeable[key] = []

        if location == 'right':
            themeable['strip_background_y'].append(rect)
            themeable['strip_text_y'].append(text)
        else:
            themeable['strip_background_x'].append(rect)
            themeable['strip_text_x'].append(text)
