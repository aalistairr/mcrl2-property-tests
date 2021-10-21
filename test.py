#!/usr/bin/env python3

# Author: Alistair Geesing

from functools import lru_cache
import sys
import os
import glob
from typing import List, NamedTuple, Tuple, Union
from enum import Enum
import subprocess


MCRL2_DOT_APP_BIN_DIR = '/Applications/mCRL2.app/Contents/bin'
TEST_TEMPLATE_FILENAME = 'test-template.mcrl2'
DIRECTIVE_PREFIX = b'%! '
PROP_DIRECTIVE = b'PROP '


class Expect(Enum):
    PASS = 0
    FAIL = 1

    def directive(self) -> bytes:
        if self == Expect.PASS:
            return b'PASS '
        elif self == Expect.FAIL:
            return b'FAIL '
        else:
            raise Exception('unreachable')


class TestTrace(NamedTuple):
    src_filename: str
    src_line_no: int
    property_filenames: List[str]
    expect: Expect
    trace: bytes


def main() -> None:
    if os.path.exists(MCRL2_DOT_APP_BIN_DIR):
        os.environ['PATH'] += f':{MCRL2_DOT_APP_BIN_DIR}'

    total, failed = 0, 0
    if len(sys.argv) == 1:
        for filename in sorted(glob.glob("properties/*.mcf") + glob.glob("properties/*.mcf-pc")):
            if os.path.isfile(filename):
                subtotal, subfailed = perform_tests(filename)
                total += subtotal
                failed += subfailed
    elif len(sys.argv) == 2:
        filename = sys.argv[1]
        if not os.path.isfile(filename):
            print(f'{filename} is not a file', file=sys.stdout)
            exit(255)
        total, failed = perform_tests(filename)
    else:
        assert len(sys.argv) > 0
        print(f'Usage: {sys.argv[0]} [FILE]', file=sys.stdout)
        exit(255)

    print(f'\nDone!\nTotal tests: {total}\nFailed tests: {failed}', file=sys.stdout)


def perform_tests(filename: str) -> Tuple[int, int]:
    total = 0
    failed = 0

    test_traces = extract_test_traces(filename)

    if len(test_traces) > 0:
        print(f'Running {len(test_traces)} tests in `{filename}`', file=sys.stdout)
    else:
        print(f'No tests in `{filename}`', file=sys.stdout)

    for test_trace in test_traces:
        total += 1

        r = run_test_trace(test_trace)
        if not r:
            failed += 1
            if r == False:
                print(f'\tThe test on line {test_trace.src_line_no} did not succeed', file=sys.stdout)

    return (total, failed)


@lru_cache(maxsize=8)
def read_file(filename: str) -> bytes:
    with open(filename, 'rb') as f:
        return f.read()


def extract_test_traces(filename: str) -> List[TestTrace]:
    property_filenames = [filename] if not filename.endswith('.mcf-pc') else [pf for pf in [parse_property_filename(filename, line) for line in read_file(filename).splitlines()] if pf is not None]
    return [tt for tt in [parse_test_trace(filename, line_no + 1, property_filenames, line) for line_no, line in enumerate(read_file(filename).splitlines())] if tt is not None]


def parse_property_filename(filename: str, line: bytes) -> Union[None, str]:
    if not line.startswith(DIRECTIVE_PREFIX):
        return
    line = line[len(DIRECTIVE_PREFIX):]

    if not line.startswith(PROP_DIRECTIVE):
        return
    line = line[len(PROP_DIRECTIVE):]

    return os.path.join(os.path.dirname(filename), line.decode('utf-8') + '.mcf')


def parse_test_trace(filename: str, line_no: int, property_filenames: List[str], line: bytes) -> Union[None, TestTrace]:
    if not line.startswith(DIRECTIVE_PREFIX):
        return
    line = line[len(DIRECTIVE_PREFIX):]

    expect = parse_expect(line)
    if expect is None:
        if not line.startswith(PROP_DIRECTIVE):
            print(f'WARNING - {filename}:{line_no} - unknown directive', file=sys.stdout)
        return
    line = line[len(expect.directive()):]

    return TestTrace(filename, line_no, property_filenames, expect, line)


def parse_expect(line: bytes) -> Union[None, TestTrace]:
    if line.startswith(Expect.PASS.directive()):
        return Expect.PASS
    elif line.startswith(Expect.FAIL.directive()):
        return Expect.FAIL
    else:
        return None


def run_test_trace(test_trace: TestTrace) -> Union[None, bool]:
    test_file = create_test_file(test_trace)
    mcrl22lps = subprocess.run(['mcrl22lps'], input=test_file, capture_output=True)
    if not check_command(test_trace, 'mcrl22lps', mcrl22lps):
        return
    lps = mcrl22lps.stdout

    final_result = True
    for property_filename in test_trace.property_filenames:
        test_result = check_property(test_trace, lps, property_filename) or False
        final_result &= test_result
        if not test_result and test_trace.expect == Expect.PASS and len(test_trace.property_filenames) > 1:
            print(f'\tThe test on line {test_trace.src_line_no} did not succeed for the property `{property_filename}', file=sys.stdout)

    return final_result == (test_trace.expect == Expect.PASS)


def check_property(test_trace: TestTrace, lps: bytes, property_filename: str) -> Union[None, bool]:
    lps2pbes = subprocess.run(['lps2pbes', f'--formula={property_filename}'], input=lps, capture_output=True)
    if not check_command(test_trace, 'lps2pbes', lps2pbes):
        return
    pbessolve = subprocess.run(['pbessolve'], input=lps2pbes.stdout, capture_output=True)
    if not check_command(test_trace, 'pbessolve', pbessolve):
        return

    result = pbessolve.stdout.rstrip()
    if result == b'true':
        return True
    elif result == b'false':
        return False
    else:
        print(f'\tpbessolve returned unexpected output:', pbessolve, file=sys.stdout)
        return False


def create_test_file(test_trace: TestTrace) -> bytes:
    x = b''
    x += read_file(TEST_TEMPLATE_FILENAME)
    x += b'\ninit '
    x += test_trace.trace
    x += b';'
    return x


def check_command(test_trace: TestTrace, command_name: str, completed_process: subprocess.CompletedProcess[bytes]) -> bool:
    if completed_process.returncode == 0:
        return True

    print(f'\nThe test on line {test_trace.src_line_no} caused `{command_name}` to fail. stderr:', file=sys.stderr)
    sys.stderr.buffer.write(completed_process.stderr)
    sys.stderr.buffer.write(b'\n')
    sys.stderr.buffer.flush()

    return False


if __name__ == '__main__':
    main()
