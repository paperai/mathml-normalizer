import sys
import os
import subprocess
import tempfile

import bs4
from bs4 import BeautifulSoup


EMPTY_TAGS = ['mtd', 'mprescripts', 'none']
POSITIONAL_TAGS = {
    'msub': 2,
    'msup': 2,
    'msubsup': 3,
    'mover': 2,
    'munder': 2,
    'munderover': 3,
    'mmultiscripts': None,
    'mfrac': 2,
}


class Normalizer(object):

    def normalize(self, soup):
        self.dfs(soup)
        return soup

    def dfs(self, t):
        if isinstance(t, bs4.element.Tag):
            if t.name == 'annotation':
                t.extract()
            elif t.name == 'semantics' and len(list(t.children)) == 1:
                t.replace_with_children()
            else:
                for c in list(t.children):
                    self.dfs(c)

            merge_mi(t)

            # remove <mrow> if there is only one child
            if t.name == 'mrow' and len(list(t.children)) == 1:
                t.replace_with_children()

            remove_empty_tag(t)

            # normalize table
            remove_empty_row(t)
            remove_empty_columns(t)
            remove_single_table(t)

            validate(t)
        else:
            t.string = normalize_characters(t.string.strip())

            # remove function application
            if t.string == '\u2061':
                t.string = ''


def normalize_characters(s):
    s = s.replace('−', '-')
    s = s.replace('\u2009', ' ')
    return s


def merge_mi(t):
    # merge successive <mi>
    if t.name not in POSITIONAL_TAGS:
        last_c = None
        for c in list(t.children):
            if c.name == 'mi' and last_c is not None:
                if last_c.name == 'mi':
                    c.string = last_c.string + c.string
                    last_c.extract()
            last_c = c


def remove_single_table(t):
    # remove unnecessary <mtable><mtr><mtd>

    def _check_single_name(tag, name):
        return isinstance(tag, bs4.element.Tag) and tag.name == name and len(list(tag.children)) == 1

    for c in list(t.children):
        if _check_single_name(c, 'mtable'):
            gc = list(c.children)[0]
            if _check_single_name(gc, 'mtr'):
                ggc = list(gc.children)[0]
                if isinstance(ggc, bs4.element.Tag) and ggc.name == 'mtd':
                    # remove <mtable><mtr><mtd>
                    ggc.replace_with_children()
                    gc.replace_with_children()
                    c.replace_with_children()


def remove_empty_tag(t):
    if len(list(t.children)) == 0 and t.name not in EMPTY_TAGS:
        if t.parent is not None and t.parent not in POSITIONAL_TAGS:
            t.extract()


def remove_empty_row(t):
    if t.name == 'mtr' and all(map(is_empty_mtd, t.children)):
        t.extract()


def remove_empty_columns(t):
    if t.name == 'mtable':
        n_columns = max(map(lambda c: len(list(c.children)), t.children))
        is_empty = [True] * n_columns
        for row in t.children:
            for j, cell in enumerate(row.children):
                is_empty[j] = is_empty[j] and is_empty_mtd(cell)
        for row in t.children:
            for j, cell in enumerate(row.children):
                if is_empty[j]:
                    cell.extract()


def is_empty_mtd(t):
    return t.name == 'mtd' and len(list(t.children)) == 0


def validate(t):
    n_children = POSITIONAL_TAGS.get(t.name, None)
    if n_children is not None:
        if n_children != len(list(t.children)):
            raise RuntimeError('{} has an invalid number of children'.format(t.name))




def add_namespace(xml):
    # insert namespace declaration
    xml = xml.replace('<mml:math>', '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML">')
    xml = xml.replace('<math', '<math xmlns:mml="http://www.w3.org/1998/Math/MathML"')
    return xml


def run_mathml_can(path, jar, config, logging_properties=None):
    args = ['java']
    if logging_properties:
        args += ['-Djava.util.logging.config.file=' + logging_properties]
    args += ['-jar', jar]
    if config is not None:
        args.append('-config')
        args.append(config)
    args.append(path)
    with subprocess.Popen(args, stdout=subprocess.PIPE) as proc:
        output, _ = proc.communicate()
        return output.decode('utf-8')


def main(args):
    normalizer = Normalizer()
    with open(args.xml) as f_in:
        tmp_file = tempfile.mkstemp()
        try:
            with os.fdopen(tmp_file[0], 'w') as f_tmp:
                print(add_namespace(f_in.read()), file=f_tmp)

            xml = run_mathml_can(tmp_file[1], args.jar, args.config, logging_properties=args.logging_properties)
            os.remove(tmp_file[1])

            soup = BeautifulSoup(xml, 'xml')
            soup = normalizer.normalize(soup)
            if args.pretty_print:
                print(soup.prettify())
            else:
                print(soup)
        except Exception as e:
            print('Error while processing: ' + args.xml, file=sys.stderr)
            raise e


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Normalize MathML file')
    parser.add_argument('xml', help='MathML file to normalize')
    parser.add_argument('--jar', default='MathMLCan/target/mathml-canonicalizer-1.3.1-jar-with-dependencies.jar', help='MathMLCan jar file')
    parser.add_argument('--config', default='config.xml', help='MathMLCan config file')
    parser.add_argument('--pretty-print', action='store_true', help='pretty-print output')
    parser.add_argument('--logging-properties', help='Java property file for logging')

    main(parser.parse_args())
