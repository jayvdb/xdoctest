# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals
import warnings
import sys
import six
from os.path import exists
from xdoctest import static_analysis as static
from xdoctest import docscrape_google
from xdoctest import utils
from xdoctest import doctest_parser


class ExitTestException(Exception):
    pass


class DocTest(object):
    """
    Holds information necessary to execute and verify a doctest

    Example:
        >>> package_name = 'xdoctest'
        >>> testables = parse_doctestables(package_name)
        >>> self = next(testables)
        >>> print(self.want)
        >>> print(self.want)
        >>> print(self.valid_testnames)
    """

    def __init__(self, modpath, callname, docsrc, num=0, lineno=0):
        self.modpath = modpath
        if modpath is None:
            self.modname = '<none>'
        else:
            self.modname = static.modpath_to_modname(modpath)
        if callname is None:
            self.callname = '<string>'
        else:
            self.callname = callname
        self.docsrc = docsrc
        self.lineno = lineno
        self.num = num
        self._parts = None
        self.ex = None
        self.outputs = []
        self.globs = {}

    def __nice__(self):
        parts = []
        parts.append(self.modname)
        parts.append('%s:%s' % (self.callname, self.num))
        if self.lineno is not None:
            parts.append('ln %s' % (self.lineno))
        return ' '.join(parts)

    def __repr__(self):
        classname = self.__class__.__name__
        devnice = self.__nice__()
        return '<%s(%s) at %s>' % (classname, devnice, hex(id(self)))

    def __str__(self):
        classname = self.__class__.__name__
        devnice = self.__nice__()
        return '<%s(%s)>' % (classname, devnice)

    def is_disabled(self):
        """
        Checks for comment directives on the first line of the doctest
        """
        import re
        m = re.match(r'>>>\s*#\s*DISABLE', self.docsrc, flags=re.IGNORECASE)
        return m is not None

    @property
    def unique_callname(self):
        return self.callname + ':' + str(self.num)

    @property
    def valid_testnames(self):
        return {
            self.callname,
            self.unique_callname,
        }

    def format_src(self, linenums=True, colored=True):
        """
        Adds prefix and line numbers to a doctest

        Example:
            >>> package_name = 'xdoctest'
            >>> testables = parse_doctestables(package_name)
            >>> self = next(testables)
            >>> self._parse()
            >>> print(self.format_src())
            >>> print(self.format_src(linenums=False, colored=False))
            >>> assert not self.is_disabled()
        """
        # return '\n'.join([p.source for p in self._parts])
        part_source = []
        for part in self._parts:
            doctest_src = part.source
            doctest_src = utils.indent(doctest_src, '>>> ')
            doctest_src = '\n'.join(part.orig_lines)
            doctest_want = part.want if part.want else ''
            if linenums:
                new_lines = []
                count = 1 + part.line_offset
                for count, line in enumerate(doctest_src.splitlines(), start=count):
                    new_lines.append('%3d %s' % (count, line))
                if doctest_want:
                    for count, line in enumerate(doctest_want.splitlines(), start=count):
                        new_lines.append('    %s' % (line))
                new = '\n'.join(new_lines)
            else:
                if doctest_want:
                    new = doctest_src + '\n' + doctest_want
                else:
                    new = doctest_src
            if colored:
                new = utils.highlight_code(new, 'python')
            part_source.append(new)
        full_source = ''.join(part_source)
        return full_source

    def _parse(self):
        """
        Divide the given string into examples and intervening text.

        Example:
            >>> s = 'I am a dummy example with three parts'
            >>> x = 10
            >>> print(s)
            I am a dummy example with three parts
            >>> s = 'My purpose it so demonstrate how wants work here'
            >>> print('The new want applies ONLY to stdout')
            >>> print('given before the last want')
            >>> '''
                this wont hurt the test at all
                even though its multiline '''
            >>> y = 20
            The new want applies ONLY to stdout
            given before the last want
            >>> # Parts from previous examples are executed in the same context
            >>> print(x + y)
            30

            this is simply text, and doesnt apply to the previous doctest the
            <BLANKLINE> directive is still in effect.

        Example:
            >>> from xdoctest import doctest_parser
            >>> from xdoctest import docscrape_google
            >>> from xdoctest import core
            >>> docstr = core.DocTest._parse.__doc__
            >>> blocks = docscrape_google.split_google_docblocks(docstr)
            >>> doclineno = core.DocTest._parse.__code__.co_firstlineno
            >>> key, (docsrc, offset) = blocks[-2]
            >>> lineno = doclineno + offset
            >>> self = core.DocTest(core.__file__, '_parse',  docsrc, 0, lineno)
            >>> self._parse()
            >>> assert len(self._parts) >= 3
            >>> #p1, p2, p3 = self._parts
            >>> self.run()
        """
        self._parts = doctest_parser.DoctestParser().parse(self.docsrc)
        self._parts = [p for p in self._parts
                       if not isinstance(p, six.string_types)]

    def run(self, verbose=None):
        """
        Executes the doctest

        TODO:
            * break src and want into multiple parts

        Notes:
            * There is no difference between locals/globals in exec context
            Only pass in one dict, otherwise there is weird behavior
            References: https://bugs.python.org/issue13557
        """
        if verbose is None:
            verbose = 2
        self._parse()
        self.pre_run(verbose)
        # Prepare for actual test run
        test_globals = self.globs
        self.outputs = []
        try:
            for part in self._parts:
                mode = 'eval' if part.use_eval else 'exec'
                code = compile(part.source, '<string>', mode)
                cap = utils.CaptureStdout(supress=verbose <= 1)
                with cap:
                    if part.use_eval:
                        result = eval(code, test_globals)
                    else:
                        exec(code, test_globals)
                        result = None
                assert cap.text is not None
                self.outputs.append(cap.text)
                try:
                    part.check_stdout_got_vs_want(cap.text)
                except AssertionError as ex1:
                    if part.use_eval:
                        # FIXME: got message might be confusing with this logic
                        try:
                            part.check_eval_got_vs_want(result)
                        except AssertionError as ex2:
                            raise AssertionError('ex1 = ' + str(ex1) + '\n ex2 =' + str(ex2))
                    else:
                        raise
        # Handle anything that could go wrong
        except ExitTestException:  # nocover
            if verbose > 0:
                print('Test gracefully exists')
        except Exception as ex:  # nocover
            self.ex = ex
            self.report_failure(verbose)
            raise

        return self.post_run(verbose)

    @property
    def cmdline(self):
        # TODO: move to pytest
        return 'python -m ' + self.modname + ' ' + self.unique_callname

    def pre_run(self, verbose):
        if verbose >= 1:
            print('============')
            print('* BEGIN EXAMPLE : {}'.format(self.callname))
            print(self.cmdline)
            if verbose >= 2:
                print(self.format_src())
        else:  # nocover
            sys.stdout.write('.')
            sys.stdout.flush()

    def repr_failure(self, verbose=1):
        # TODO: print out nice line number
        lines = []
        if verbose > 0:
            lines += [
                '',
                'report failure',
                self.cmdline,
                # self.format_src(),
            ]
        lines += [
            '* FAILURE: {}, {}'.format(self.callname, type(self.ex)),
            ''.join(self.outputs),
        ]
        # TODO: remove appropriate amount of traceback
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # exc_traceback = exc_traceback.tb_next
        # six.reraise(exc_type, exc_value, exc_traceback)
        return '\n'.join(lines)

    def report_failure(self, verbose):
        text = self.repr_failure(verbose=verbose)
        print(text)

    def post_run(self, verbose):
        if self.ex is None and verbose >= 1:
            # out_text = ''.join(self.outputs)
            # if out_text is not None:
            #     assert isinstance(out_text, six.text_type), 'do not use ascii'
            # try:
            #     print(out_text)
            # except UnicodeEncodeError:
            #     print('Weird travis bug')
            #     print('type(out_text) = %r' % (type(out_text),))
            #     print('out_text = %r' % (out_text,))
            print('* SUCCESS: {}'.format(self.callname))
        summary = {
            'passed': self.ex is None
        }
        return summary


def parse_freeform_docstr_examples(docstr, callname=None, modpath=None,
                                   lineno=0):
    """
    Finds free-form doctests in a docstring. This is similar to the original
    doctests because these tests do not requires a google/numpy style header.

    Some care is taken to avoid enabling tests that look like disabled google
    doctests / scripts.

    Example:
        >>> from xdoctest import core
        >>> import ubelt as ub
        >>> docstr = ub.codeblock(
            '''
            freeform
            >>> doctest
            >>> hasmultilines
            whoppie
            >>> butthis is the same doctest

            >>> secondone

            Script:
                >>> special case, dont parse me

            DisableDoctest:
                >>> special case, dont parse me
                want

            AnythingElse:
                >>> general case, parse me
                want
            ''')
        >>> examples = list(parse_freeform_docstr_examples(docstr))
        >>> assert len(examples) == 3
    """
    import textwrap

    def doctest_from_parts(parts, num):
        lineno_ = lineno + parts[0].line_offset
        docsrc = '\n'.join([line for p in parts for line in p.orig_lines])
        docsrc = textwrap.dedent(docsrc)
        example = DocTest(modpath, callname, docsrc, num, lineno=lineno_)
        # We've already parsed, so we dont need to do it again
        example._parts = parts
        return example

    respect_google_headers = True
    if respect_google_headers:
        # These are google doctest patterns that disable a test from being run
        # try to respect these even in freeform mode.
        special_skip_patterns = [
            'DisableDoctest:',
            'SkipDoctest:',
            'Ignore:',
            'Script:',
        ]
    else:
        special_skip_patterns = []
    special_skip_patterns_ = tuple([
        p.lower() for p in special_skip_patterns
    ])

    def _special_skip(prev):
        return (special_skip_patterns_ and
                isinstance(prev, six.string_types) and
                prev.strip().lower().startswith(special_skip_patterns_))

    # parse into doctest and plaintext parts
    all_parts = doctest_parser.DoctestParser().parse(docstr)

    parts = []
    num = 0
    prev = None
    for part in all_parts:
        if isinstance(part, six.string_types):
            # Part is a plaintext
            if parts:
                example = doctest_from_parts(parts, num)
                yield example
                num += 1
                parts = []
        else:
            # Part is a doctest
            if _special_skip(prev):
                continue
            parts.append(part)
        prev = part
    if parts:
        example = doctest_from_parts(parts, num)
        yield example


def parse_google_docstr_examples(docstr, callname=None, modpath=None,
                                 lineno=None):
    """
    Parses Google-style doctests from a docstr and generates example objects

    TODO: generalize to not just google-style
    """
    try:
        blocks = docscrape_google.split_google_docblocks(docstr)
        example_blocks = []
        for type, block in blocks:
            if type.startswith('Example'):
                example_blocks.append((type, block))
            if type.startswith('Doctest'):
                example_blocks.append((type, block))
        for num, (type, (docsrc, offset)) in enumerate(example_blocks):
            # Add one because offset applies to the google-type label
            lineno_ = lineno + offset + 1
            example = DocTest(modpath, callname, docsrc, num, lineno=lineno_)
            yield example
    except Exception as ex:  # nocover
        msg = ('Cannot scrape callname={} in modpath={}.\n'
               'Caused by={}')
        msg = msg.format(callname, modpath, ex)
        raise Exception(msg)


def module_calldefs(modpath):
    return static.parse_calldefs(fpath=modpath)


def package_calldefs(package_name, exclude=[], strict=False):
    """
    Statically generates all callable definitions in a package
    """
    modnames = static.package_modnames(package_name, exclude=exclude)
    for modname in modnames:
        modpath = static.modname_to_modpath(modname, hide_init=False)
        if not exists(modpath):  # nocover
            warnings.warn(
                'Module {} does not exist. '
                'Is it an old pyc file?'.format(modname))
            continue
        try:
            calldefs = module_calldefs(modpath=modpath)
        except SyntaxError as ex:  # nocover
            msg = 'Cannot parse module={} at path={}.\nCaused by={}'
            msg = msg.format(modname, modpath, ex)
            if strict:
                raise Exception(msg)
            else:
                warnings.warn(msg)
                continue
        else:
            yield calldefs, modpath


def parse_doctestables(package_name, exclude=[], strict=False):
    r"""
    Finds all functions/callables with Google-style example blocks

    Example:
        >>> package_name = 'xdoctest'
        >>> testables = list(parse_doctestables(package_name))
        >>> this_example = None
        >>> for example in testables:
        >>>     print(example)
        >>>     if example.callname == 'parse_doctestables':
        >>>         this_example = example
        >>> assert this_example is not None
        >>> assert this_example.callname == 'parse_doctestables'
    """
    for calldefs, modpath in package_calldefs(package_name, exclude, strict):
        for callname, calldef in calldefs.items():
            docstr = calldef.docstr
            if calldef.docstr is not None:
                lineno = calldef.doclineno
                for example in parse_google_docstr_examples(docstr, callname,
                                                            modpath,
                                                            lineno=lineno):
                    yield example
