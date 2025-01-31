# -*- coding: utf-8 -*-
"""
Utilities related to string manipulations
"""
from __future__ import print_function, division, absolute_import, unicode_literals
import six
import math
import textwrap
# import warnings
import re
import sys


def strip_ansi(text):
    r"""
    Removes all ansi directives from the string.

    References:
        http://stackoverflow.com/questions/14693701/remove-ansi
        https://stackoverflow.com/questions/13506033/filtering-out-ansi-escape-sequences

    Examples:
        >>> line = '\t\u001b[0;35mBlabla\u001b[0m     \u001b[0;36m172.18.0.2\u001b[0m'
        >>> escaped_line = strip_ansi(line)
        >>> assert escaped_line == '\tBlabla     172.18.0.2'
    """
    # ansi_escape1 = re.compile(r'\x1b[^m]*m')
    # text = ansi_escape1.sub('', text)
    # ansi_escape2 = re.compile(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?')
    ansi_escape3 = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]', flags=re.IGNORECASE)
    text = ansi_escape3.sub('', text)
    return text


def color_text(text, color):
    r"""
    Colorizes text a single color using ansii tags.

    Args:
        text (str): text to colorize
        color (str): may be one of the following: yellow, blink, lightgray,
            underline, darkyellow, blue, darkblue, faint, fuchsia, black,
            white, red, brown, turquoise, bold, darkred, darkgreen, reset,
            standout, darkteal, darkgray, overline, purple, green, teal, fuscia

    Returns:
        str: text : colorized text.
            If pygments is not installed plain text is returned.

    Example:
        >>> text = 'raw text'
        >>> from xdoctest import utils
        >>> if utils.modname_to_modpath('pygments'):
        >>>     # Colors text only if pygments is installed
        >>>     ansi_text = utils.ensure_unicode(color_text(text, 'red'))
        >>>     prefix = utils.ensure_unicode('\x1b[31')
        >>>     print('prefix = {!r}'.format(prefix))
        >>>     print('ansi_text = {!r}'.format(ansi_text))
        >>>     assert ansi_text.startswith(prefix)
        >>>     assert color_text(text, None) == 'raw text'
        >>> else:
        >>>     # Otherwise text passes through unchanged
        >>>     assert color_text(text, 'red') == 'raw text'
        >>>     assert color_text(text, None) == 'raw text'
    """
    if color is None:
        return text
    try:
        import pygments
        import pygments.console

        if sys.platform.startswith('win32'):  # nocover
            # Hack on win32 to support colored output
            import colorama
            colorama.init()

        try:
            ansi_text = pygments.console.colorize(color, text)
        except KeyError as ex:
            import warnings
            warnings.warn('unable to fine color: {!r}'.format(color))
            return text
        except Exception as ex:
            import warnings
            warnings.warn('some other issue with text color: {!r}'.format(ex))
            return text
        return ansi_text
    except ImportError:  # nocover
        import warnings
        warnings.warn('pygments is not installed, text will not be colored')
        return text


def ensure_unicode(text):
    """
    Casts bytes into utf8 (mostly for python2 compatibility)

    References:
        http://stackoverflow.com/questions/12561063/python-extract-data-from-file

    CommandLine:
        python -m xdoctest.utils ensure_unicode

    Example:
        >>> assert ensure_unicode('my ünicôdé strįng') == 'my ünicôdé strįng'
        >>> assert ensure_unicode('text1') == 'text1'
        >>> assert ensure_unicode('text1'.encode('utf8')) == 'text1'
        >>> assert ensure_unicode('ï»¿text1'.encode('utf8')) == 'ï»¿text1'
        >>> import codecs
        >>> assert (codecs.BOM_UTF8 + 'text»¿'.encode('utf8')).decode('utf8')
    """
    if isinstance(text, six.text_type):
        return text
    elif isinstance(text, six.binary_type):
        return text.decode('utf8')
    else:  # nocover
        raise ValueError('unknown input type {!r}'.format(text))


def indent(text, prefix='    '):
    r"""
    Indents a block of text

    Args:
        text (str): text to indent
        prefix (str): prefix to add to each line (default = '    ')

    Returns:
        str: indented text

    CommandLine:
        python -m xdoctest.utils ensure_unicode

    Example:
        >>> text = 'Lorem ipsum\ndolor sit amet'
        >>> prefix = '    '
        >>> result = indent(text, prefix)
        >>> assert all(t.startswith(prefix) for t in result.split('\n'))
    """
    return prefix + text.replace('\n', '\n' + prefix)


def highlight_code(text, lexer_name='python', **kwargs):
    """
    Highlights a block of text using ansi tags based on language syntax.

    Args:
        text (str): plain text to highlight
        lexer_name (str): name of language
        **kwargs: passed to pygments.lexers.get_lexer_by_name

    Returns:
        str: text : highlighted text
            If pygments is not installed, the plain text is returned.

    CommandLine:
        python -c "import pygments.formatters; print(list(pygments.formatters.get_all_formatters()))"

    Example:
        >>> text = 'import xdoctest as xdoc; print(xdoc)'
        >>> new_text = highlight_code(text)
        >>> print(new_text)
    """
    # Resolve extensions to languages
    lexer_name = {
        'py': 'python',
        'h': 'cpp',
        'cpp': 'cpp',
        'cxx': 'cpp',
        'c': 'cpp',
    }.get(lexer_name.replace('.', ''), lexer_name)
    try:
        import pygments
        import pygments.lexers
        import pygments.formatters
        import pygments.formatters.terminal
        formater = pygments.formatters.terminal.TerminalFormatter(bg='dark')
        lexer = pygments.lexers.get_lexer_by_name(lexer_name, ensurenl=False, **kwargs)
        new_text = pygments.highlight(text, lexer, formater)
    except ImportError:  # nocover
        # warnings.warn('pygments is not installed')
        new_text = text
    return new_text


def add_line_numbers(source, start=1, n_digits=None):
    """
    Prefixes code with line numbers

    Example:
        >>> print(chr(10).join(add_line_numbers(['a', 'b', 'c'])))
        1 a
        2 b
        3 c
        >>> print(add_line_numbers(chr(10).join(['a', 'b', 'c'])))
        1 a
        2 b
        3 c
    """
    was_string = isinstance(source, six.string_types)
    part_lines = source.splitlines() if was_string else source

    if n_digits is None:
        endline = start + len(part_lines)
        n_digits = math.log(max(1, endline), 10)
        n_digits = int(math.ceil(n_digits))

    src_fmt = '{count:{n_digits}d} {line}'

    part_lines = [
        src_fmt.format(n_digits=n_digits, count=count, line=line)
        for count, line in enumerate(part_lines, start=start)
    ]

    if was_string:
        return '\n'.join(part_lines)
    else:
        return part_lines


def codeblock(block_str):
    """
    Wraps multiline string blocks and returns unindented code.
    Useful for templated code defined in indented parts of code.

    Args:
        block_str (str): typically in the form of a multiline string

    Returns:
        str: the unindented string

    Example:
        >>> # Simulate an indented part of code
        >>> if True:
        ...     # notice the indentation on this will be normal
        ...     codeblock_version = codeblock(
        ...             '''
        ...             def foo():
        ...                 return 'bar'
        ...             '''
        ...         )
        ...     # notice the indentation and newlines on this will be odd
        ...     normal_version = ('''
        ...         def foo():
        ...             return 'bar'
        ...     ''')
        >>> assert normal_version != codeblock_version
        >>> print('Without codeblock')
        >>> print(normal_version)
        >>> print('With codeblock')
        >>> print(codeblock_version)
    """
    return textwrap.dedent(block_str).strip('\n')


if __name__ == '__main__':
    """
    CommandLine:
        python -m xdoctest.utils.util_str all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
