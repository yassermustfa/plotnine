from copy import copy, deepcopy

import matplotlib as mpl

from ..utils.exceptions import GgplotError
from ..utils import ggplot_options
from .themeable import make_themeable, merge_themeables
from .themeable import scalar_themeables


class theme(object):

    """
    This is an abstract base class for themes.

    In general, only complete themes should should subclass this class.


    Notes
    -----
    When subclassing there are really only two methods that need to be
    implemented.

    __init__: This should call super().__init__ which will define
    self._rcParams. Subclasses should customize self._rcParams after
    calling super().__init__. That will ensure that the rcParams are
    applied at the appropriate time.

    The other method is apply_more(ax). This method takes an axes
    object that has been created during the plot process. The theme
    should modify the axes according.

    """

    def __init__(self, complete=False, **kwargs):
        """
        Provide ggplot2 themeing capabilities.

        Parameters
        -----------
        complete : bool
            Themes that are complete will override any existing themes.
            themes that are not complete (ie. partial) will add to or
            override specific elements of the current theme.

            eg.
                theme_matplotlib() + theme_xkcd()

            will be completely determined by theme_xkcd, but

                (theme_matplotlib() +
                    theme(axis_text_x=element_text(angle=45)))

            will only modify the x axis text.

        kwargs**: themeables
            kwargs are themeables based on
            http://docs.ggplot2.org/current/theme.html.
            In addition, Python does not allow using '.' in argument
            names, so we are using '_' instead.

            For example, ggplot2 axis.ticks.y will be axis_ticks_y
            in Python ggplot.

            Many themeables are defined using theme elements i.e

                - element_line
                - element_rect
                - element_text

            These simply bind together all the aspects of a themeable
            that can be themed.
        """
        self.themeables = []
        self.complete = complete
        self._rcParams = {}
        # This is set when the figure is created,
        # it is useful at legend drawing time.
        self.figure = None
        self._params = scalar_themeables.copy()

        for name, element in kwargs.items():
            if name in scalar_themeables:
                self._params[name] = element
            else:
                self.themeables.append(
                    make_themeable(name, element))

    def apply(self, ax):
        """
        Apply this theme, then apply additional modifications in order.

        This method should not be overridden. Subclasses should override
        the apply_more method. This implementation will ensure that the
        a theme that includes partial themes will be themed properly.
        """
        # Restyle the tick lines
        for line in ax.get_xticklines() + ax.get_yticklines():
            line.set_markeredgewidth(mpl.rcParams['grid.linewidth'])

        # minor grid line
        if mpl.rcParams['axes.grid.which'] in ('minor', 'both'):
            lw = mpl.rcParams['grid.linewidth']/2.0
            ax.xaxis.grid(which='minor', linewidth=lw)
            ax.yaxis.grid(which='minor', linewidth=lw)

        self.apply_more(ax)

        # does this need to be ordered first?
        for themeable in self.themeables:
            themeable.apply(ax)

    def apply_more(self, ax):
        """
        Makes any desired changes to the axes object

        This method will be called with an axes object after plot
        has completed. Complete themes should implement this method
        if post plot themeing is required.
        """
        pass

    def setup_figure(self, figure):
        """
        Makes any desired changes to the figure object

        This method will be called once with a figure object
        before any plotting has completed. Subclasses that
        override this method should make sure that the base
        class method is called.
        """
        for themeable in self.themeables:
            themeable.setup_figure(figure)

    def apply_figure(self, figure):
        """
        Makes any desired changes to the figure object

        This method will be called once with a figure object
        after plot has completed. Subclasses that override this
        method should make sure that the base class method is
        called.
        """
        for themeable in self.themeables:
            themeable.apply_figure(figure)

    @property
    def rcParams(self):
        """
        Return rcParams dict for this theme.

        Notes
        -----
        Subclasses should not need to override this method method as long as
        self._rcParams is constructed properly.

        rcParams are used during plotting. Sometimes the same theme can be
        achieved by setting rcParams before plotting or a apply
        after plotting. The choice of how to implement it is is a matter of
        convenience in that case.

        There are certain things can only be themed after plotting. There
        may not be an rcParam to control the theme or the act of plotting
        may cause an entity to come into existence before it can be themed.

        """

        try:
            rcParams = deepcopy(self._rcParams)
        except NotImplementedError:
            # deepcopy raises an error for objects that are drived from or
            # composed of matplotlib.transform.TransformNode.
            # Not desirable, but probably requires upstream fix.
            # In particular, XKCD uses matplotlib.patheffects.withStrok
            rcParams = copy(self._rcParams)

        if self.themeables:
            for themeable in self.themeables:
                rcParams.update(themeable.rcParams)
        return rcParams

    def add_theme(self, other):
        """Add themes together.

        Subclasses should not override this method.

        This will be called when adding two instances of class 'theme'
        together.
        A complete theme will annihilate any previous themes. Partial themes
        can be added together and can be added to a complete theme.
        """
        if other.complete:
            return other
        else:
            theme_copy = deepcopy(self)
            theme_copy.themeables = merge_themeables(
                deepcopy(self.themeables),
                deepcopy(other.themeables))
            theme_copy._params.update(other._params)
            return theme_copy

    def __add__(self, other):
        if not isinstance(other, theme):
            msg = ("Adding theme failed. ",
                   "{} is not a theme").format(str(other))
            raise GgplotError(msg)
        return self.add_theme(other)

    def __radd__(self, other):
        """Subclasses should not override this method.

        This will be called in one of two ways:
        gg + theme which is translated to self=theme, other=gg
        or
        theme1 + theme2 which is translated into self=theme2, other=theme1

        """
        if not isinstance(other, theme):
            gg_copy = deepcopy(other)
            if self.complete:
                gg_copy.theme = self
            else:
                # If no theme has been added yet,
                # we modify the default theme
                gg_copy.theme = gg_copy.theme or theme_get()
                gg_copy.theme = gg_copy.theme.add_theme(self)
            return gg_copy
        # other _ self is theme + self
        else:
            # adding theme and theme here
            # other + self
            # if self is complete return self
            if self.complete:
                return self
            # else make a copy of other combined with self.
            else:
                theme_copy = deepcopy(other)
                theme_copy.themeables.append(self)
                theme_copy._params.update(other._params)
                return theme_copy


def theme_get():
    """
    Return the default theme

    The default theme is the one set (using theme_set) by
    the user. If none has been set, then theme_gray is
    the default.
    """
    from .theme_gray import theme_gray
    return ggplot_options['current_theme'] or theme_gray()


def theme_set(new):
    """
    Change the current(default) theme

    Parameters
    ----------
    new : theme
        New default theme

    Returns
    -------
    out : theme
        Previous theme
    """
    if not issubclass(new.__class__, theme):
        raise GgplotError("Expecting object to be a theme")

    out = ggplot_options['current_theme']
    ggplot_options['current_theme'] = new
    return out


def theme_update(**kwargs):
    """
    Modify elements of the current theme

    Parameters
    ----------
    kwargs : dict
        Theme elements
    """
    theme_set(theme_get() + theme(**kwargs))
