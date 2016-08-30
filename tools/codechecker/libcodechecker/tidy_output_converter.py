# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.
'''
This module is responsible for parsing clang-tidy output and generating plist
for the plist_parser module.
'''

import re
import os
import copy
import plistlib

from libcodechecker import logger

LOG = logger.get_new_logger('TIDY_OUTPUT_HANDLER')

class Note(object):
    '''
    Represents a note and also this is the base class of Message.
    '''

    def __init__(self, path, line, column, message):
        self.path = path
        self.line = line
        self.column = column
        self.message = message


    def __eq__(self, other):
        return self.path == other.path and \
               self.line == other.line and \
               self.column == other.column and \
               self.message == other.message


    def __str__(self):
        return ('path=%s, line=%d, column=%s, message=%s') % \
               (self.path, self.line, self.column, self.message)


class Message(Note):
    '''
    Represents a clang-tidy message with an optional fixit message.
    '''

    def __init__(self, path, line, column, message, checker, fixits=None, notes=None):
        super(Message, self).__init__(path, line, column, message)
        self.checker = checker
        self.fixits = fixits if fixits else []
        self.notes = notes if notes else []


    def __eq__(self, other):
        return super(Message, self).__eq__(other) and \
               self.checker == other.checker and \
               self.fixits == other.fixits and \
               self.notes == other.notes


    def __str__(self):
        return ('%s, checker=%s, fixits=%s, notes=%s') % \
               (super(Message, self).__str__(), self.checker,
               [str(fixit) for fixit in self.fixits],
               [str(note) for note in self.notes])


class OutputParser(object):
    '''
    Parser for clang-tidy console output.
    '''

    # Regex for parsing a clang-tidy message
    message_line_re = re.compile(
        # File path followed by a ':'
        '^(?P<path>[\S]+):'
        # Line number followed by a ':'
        '(?P<line>\d+):'
        # Column number followed by a ':' and a space
        '(?P<column>\d+):\ '
        # Severity followed by a ':'
        '(?P<severity>\w+):'
        # Checker message
        '(?P<message>[\S \t]+)\s*'
        # Checker name
        '\[(?P<checker>.*)\]')

    # Matches a note
    note_line_re = re.compile(
        # File path followed by a ':'
        '^(?P<path>[\S]+):'
        # Line number followed by a ':'
        '(?P<line>\d+):'
        # Column number followed by a ':' and a space
        '(?P<column>\d+):\ '
        # Severity == note
        'note:'
        # Checker message
        '(?P<message>.*)')

    def __init__(self):
        self.messages = []


    def parse_messages_from_file(self, path):
        '''
        Parse clang-tidy output dump (redirected output).
        '''

        with open(path, 'r') as file:
            return self.parse_messages(file)

    def parse_messages(self, tidy_out):
        '''
        Parse the given clang-tidy output. This method calls iter(tidy_out).
        The iterator should return lines.

        Parameters:
            tidy_out: something iterable (e.g.: a file object)
        '''

        titer = iter(tidy_out)
        try:
            next_line = titer.next()
            while True:
                message, next_line = self._parse_message(titer, next_line)
                if message != None:
                    self.messages.append(message)
        except StopIteration:
            pass

        return self.messages

    def _parse_message(self, titer, line):
        '''
        Parse the given line. Returns a (message, next_line) pair or throws a
        StopIteration. The message could be None.

        Parameters:
            titer: clang-tidy output iterator
            line: the current line
        '''

        match = OutputParser.message_line_re.match(line)
        if match is None:
            return None, titer.next()

        message = Message(
            os.path.abspath(match.group('path')),
            int(match.group('line')),
            int(match.group('column')),
            match.group('message').strip(),
            match.group('checker').strip())

        try:
            line = titer.next()
            line = self._parse_code(message, titer, line)
            line = self._parse_fixits(message, titer, line)
            line = self._parse_notes(message, titer, line)

            return message, line
        except StopIteration:
            return message, line


    def _parse_code(self, message, titer, line):
        # eat code line
        if OutputParser.note_line_re.match(line) or \
           OutputParser.message_line_re.match(line):
            LOG.debug("Unexpected line: %s. Expected a code line!" % line)
            return line

        # eat arrow line
        # FIXME: range support?
        line = titer.next()
        if '^' not in line:
            LOG.debug("Unexpected line: %s. Expected an arrow line!" % line)
            return line
        return titer.next()


    def _parse_fixits(self, message, titer, line):
        '''Parses fixit messages'''

        while OutputParser.message_line_re.match(line) is None and \
              OutputParser.note_line_re.match(line) is None:
            message_text = line.strip()
            if message_text == '':
                continue

            message.fixits.append(Note(message.path, message.line,
                line.find(message_text) + 1, message_text))
            line = titer.next()
        return line


    def _parse_notes(self, message, titer, line):
        '''Parses note messages'''

        while OutputParser.message_line_re.match(line) is None:
            match = OutputParser.note_line_re.match(line)
            if match is None:
                LOG.debug("Unexpected line: %s" % line)
                return titer.next()

            message.notes.append(Note(os.path.abspath(match.group('path')),
                                      int(match.group('line')),
                                      int(match.group('column')),
                                      match.group('message').strip()))
            line = titer.next()
            line = self._parse_code(message, titer, line)
        return line


class PListConverter(object):
    '''
    clang-tidy messages to plist converter.
    '''

    def __init__(self):
        self.plist = {
            'files'         : [],
            'diagnostics'   : []
        }


    def _add_files_from_messages(self, messages):
        '''
        Adds the new files from the given message array to the plist's "files"
        key, and returns a path to file index dictionary.
        '''

        fmap = {}
        for message in messages:
            try:
                # This file is already in the plist
                idx = self.plist['files'].index(message.path)
                fmap[message.path] = idx
            except ValueError:
                # New file
                fmap[message.path] = len(self.plist['files'])
                self.plist['files'].append(message.path)

            # collect file paths from the message notes
            for nt in message.notes:
                try:
                    # This file is already in the plist
                    idx = self.plist['files'].index(nt.path)
                    fmap[nt.path] = idx
                except ValueError:
                    # New file
                    fmap[nt.path] = len(self.plist['files'])
                    self.plist['files'].append(nt.path)

        return fmap


    def _add_diagnostics(self, messages, fmap):
        '''
        Adds the messages to the plist as diagnostics.
        '''

        for message in messages:
            diag = PListConverter._create_diag(message, fmap)
            self.plist['diagnostics'].append(diag)


    @staticmethod
    def _get_checker_category(checker):
        '''
        Returns the check's category.
        '''

        parts = checker.split('-')
        if len(parts) == 0:
            # I don't know if it's possible
            return 'unknown'
        else:
            return parts[0]


    @staticmethod
    def _create_diag(message, fmap):
        '''
        Creates a new plist diagnostic from a single clang-tidy message.
        '''

        diag = {}
        diag['location'] = PListConverter._create_location(message, fmap)
        diag['check_name'] = message.checker
        diag['description'] = message.message
        diag['category'] = PListConverter._get_checker_category(message.checker)
        diag['type'] = 'clang-tidy'
        diag['path'] = [PListConverter._create_event_from_note(message, fmap)]

        PListConverter._add_fixits(diag, message, fmap)
        PListConverter._add_notes(diag, message, fmap)

        return diag


    @staticmethod
    def _create_location(note, fmap):
        return {
            'line' : note.line,
            'col'  : note.column,
            'file' : fmap[note.path]
        }


    @staticmethod
    def _create_event_from_note(note, fmap):
        return {
            'kind'      : 'event',
            'location'  : PListConverter._create_location(note, fmap),
            'depth'     : 0, # I don't know WTF is this
            'message'   : note.message
        }


    @staticmethod
    def _create_edge(start_note, end_note, fmap):
        start_loc = PListConverter._create_location(start_note, fmap)
        end_loc = PListConverter._create_location(end_note, fmap)
        return {
            'start' : [start_loc, start_loc],
            'end'   : [end_loc, end_loc]
        }


    @staticmethod
    def _add_fixits(diag, message, fmap):
        '''
        Adds fixits as events to the diagnostics.
        '''

        for fixit in message.fixits:
            mf = copy.deepcopy(fixit)
            mf.message = '%s (fixit)' % fixit.message
            diag['path'].append(PListConverter._create_event_from_note(
                mf, fmap))


    @staticmethod
    def _add_notes(diag, message, fmap):
        '''
        Adds notes as events to the diagnostics. It also creates edges between
        the notes.
        '''

        edges = []
        last = None
        for note in message.notes:
            if last is not None:
                edges.append(PListConverter._create_edge(last, note, fmap))
            diag['path'].append(PListConverter._create_event_from_note(
                note, fmap))
            last = note

        diag['path'].append({
            'kind'  : 'control',
            'edges' : edges
        })


    def add_messages(self, messages):
        '''
        Adds the given clang-tidy messages to the plist.
        '''

        fmap = self._add_files_from_messages(messages)
        self._add_diagnostics(messages, fmap)


    def write_to_file(self, path):
        '''
        Writes out the plist XML to the given path.
        '''

        with open(path, 'wb') as file:
            self.write(file)


    def write(self, file):
        '''
        Writes out the plist XML using the given file object.
        '''

        plistlib.writePlist(self.plist, file)
