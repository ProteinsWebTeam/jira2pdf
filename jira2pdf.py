#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import base64
import getpass
import json
import os
import re
import sys
from urllib import error, parse, request
import xml.etree.ElementTree as ET

from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics, ttfonts
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph


COLORS = [
    '#bd7446',
    '#b65cbf',
    '#58b758',
    '#c75980',
    '#a3b444',
    '#757dc9',
    '#d19c3f',
    '#4eb29d',
    '#d04d41',
    '#667a36'
]
DEFAULT_COLOR = '#eeeeee'


def load_conf(filename):
    try:
        with open(filename, 'rt') as fh:
            config = json.load(fh)
    except FileNotFoundError:
        sys.stderr.write('No such file or directory: {}\n'.format(filename))
        exit(1)
    except json.JSONDecodeError:
        sys.stderr.write('Invalid JSON format: {}\n'.format(filename))
        exit(1)
    else:
        return config


def _input(prompt, hide=False):
    s = ''

    while not s:
        if hide:
            s = getpass.getpass(prompt)
        else:
            s = input(prompt)

    return s


class Issue:
    def __init__(self, key, summary, description, reporter, **kwargs):
        self.key = key
        self.summary = summary
        self.description = description
        self.reporter = reporter

        self.components = kwargs.get('components', [])
        self.estimate = kwargs.get('estimate')
        self.assignee = kwargs.get('assignee')
        self.priority = kwargs.get('priority')


class JIRAClient:
    def __init__(self, server, user, passwd, version='2'):
        self.server = '{}/rest/api/{}'.format(server.rstrip('/'), version)
        self.user = user
        self.passwd = passwd

        if not self._poke():
            exit(1)

    @property
    def headers(self):
        return {
            'Authorization': b'Basic ' + base64.b64encode('{}:{}'.format(self.user, self.passwd).encode())
        }

    def _poke(self):
        url = '{}/myself'.format(self.server)
        req = request.Request(url, headers=self.headers)

        try:
            response = request.urlopen(req).read().decode()
        except error.HTTPError as e:
            if e.code == 401:
                sys.stderr.write('Authentication failed with user: {}\n'.format(self.user))
            elif e.code == 403:
                # Happens after too many failed connections: user has to log in on the web app (captcha required)
                sys.stderr.write('Authentication denied with user: {}\n'.format(self.user))
            elif e.code == 404:
                sys.stderr.write('JIRA server not found at: {}\n'.format(self.server))
            else:
                sys.stderr.write('Unknown error\n')
            return False
        else:
            return True

    def get(self, project, version, priority_field=None, custom_components=list()):
        issues = []

        data = parse.urlencode({
            'jql': 'project="{}" AND fixVersion="{}"'.format(project, version),
            'startAt': 0,
            'maxResults': 1000
        })

        req = request.Request('{}/search?{}'.format(self.server, data), headers=self.headers)

        try:
            response = request.urlopen(req)
            data = json.loads(response.read().decode())
        except error.HTTPError as e:
            pass
        except json.JSONDecodeError:
            pass
        else:
            # todo: handle pagination (if maxResults < total)
            for obj in data['issues']:
                if obj['fields']['issuetype']['name'] == 'Story':
                    key = obj['key']
                    summary = obj['fields']['summary']
                    description = obj['fields']['description']
                    reporter = obj['fields']['reporter']['displayName']

                    components = [c['name'] for c in obj['fields']['components']]
                    estimate = obj['fields']['aggregatetimeestimate']
                    try:
                        assignee = obj['fields']['assignee']['displayName']
                    except TypeError:
                        assignee = None

                    if priority_field:
                        try:
                            priority = int(float(obj['fields'][priority_field]))
                        except (KeyError, TypeError, ValueError):
                            priority = None
                    else:
                        priority = None

                    # Rename components
                    if custom_components:
                        new_components = []
                        for cmpt in components:
                            for custom_cmpt in custom_components:
                                if custom_cmpt.get('pattern'):
                                    pattern = r'{}'.format(custom_cmpt['pattern'])

                                    if re.search(pattern, cmpt, re.I):
                                        cmpt = custom_cmpt['name']
                                        break

                            new_components.append(cmpt)

                        components = list(set(new_components))

                    issues.append(Issue(key, summary, description, reporter,
                                        components=components, estimate=estimate,
                                        assignee=assignee, priority=priority))

        return issues


def gen_pdf(issues, output, components=list()):
    components = {c['name']: c.get('color') for c in components}

    regular = os.path.join(os.path.dirname(__file__), 'inc', 'OpenSans-Regular.ttf')
    bold = os.path.join(os.path.dirname(__file__), 'inc', 'OpenSans-Bold.ttf')
    pdfmetrics.registerFont(ttfonts.TTFont('OpenSans', regular))
    pdfmetrics.registerFont(ttfonts.TTFont('OpenSansBold', bold))

    all_components = list(set(c for i in issues for c in i.components))
    palette = {}
    i = 0
    for c in sorted(all_components):
        color = components.get(c)
        if c in components:
            palette[c] = color
        else:
            try:
                color = COLORS[i]
            except IndexError:
                color = DEFAULT_COLOR
            finally:
                palette[c] = color

    canvas = Canvas(output, pagesize=A4)
    page_width, page_height = A4

    tile_width = 400
    tile_height = 280
    x_pos = page_width / 2 - tile_width / 2
    y_pos = page_height - 10

    style1 = ParagraphStyle('summary',
                            fontName='OpenSansBold',
                            fontSize=20,
                            leading=20,
                            alignment=TA_LEFT,
                            textColor='#000000')

    style2 = ParagraphStyle('desc',
                            fontName='OpenSans',
                            fontSize=12,
                            leading=12,
                            alignment=TA_LEFT,
                            textColor='#333333')

    style3 = ParagraphStyle('people',
                            fontName='OpenSans',
                            fontSize=14,
                            leading=14,
                            alignment=TA_LEFT,
                            textColor='#000000')

    style4 = ParagraphStyle('misc',
                            fontName='OpenSans',
                            fontSize=13,
                            leading=13,
                            alignment=TA_RIGHT,
                            textColor='#000000')

    for i, issue in enumerate(issues):
        try:
            c = issue.components[0]
        except IndexError:
            color = DEFAULT_COLOR
        else:
            color = palette[c]

        canvas.setStrokeColor(color)
        canvas.setFillColor(color)
        canvas.setLineWidth(1)
        canvas.rect(x_pos, y_pos, tile_width, -tile_height, stroke=True, fill=False)
        canvas.rect(x_pos, y_pos, 8, -tile_height, stroke=False, fill=True)
        canvas.setFillColor('#000000')
        canvas.setFont("OpenSansBold", 28)
        canvas.drawString(x_pos + 15, y_pos - 25, issue.key)

        canvas.setFont("OpenSans", 14)
        canvas.drawString(x_pos + 15, y_pos - 45, ', '.join(issue.components))
        y_ori = y_pos
        y_pos -= 45

        p = Paragraph(issue.summary, style1)
        w, h = p.wrapOn(canvas, tile_width - 30, 150)
        p.drawOn(canvas, x_pos + 15, y_pos - h - 15)
        y_pos -= h + 15

        if issue.description:
            lines = issue.description.split('\n')
            if len(lines) > 8:
                desc = '\n'.join(lines[:8]) + '\n...'
            else:
                desc = issue.description

            if len(desc) <= 250:
                desc = desc
            else:
                desc = desc[:250] + '...'

            try:
                p = Paragraph(desc.replace('\n', '<br/>'), style2)
            except ValueError:
                pass
            else:
                w, h = p.wrapOn(canvas, tile_width - 30, 150)
                p.drawOn(canvas, x_pos + 15, y_pos - h - 5)
                y_pos -= h + 5

        if issue.assignee:
            text = 'Assignee: {}<br/>Reporter: {}'.format(issue.assignee, issue.reporter)
        else:
            text = 'Reporter: {}'.format(issue.reporter)

        p = Paragraph(text, style3)
        w, h = p.wrapOn(canvas, tile_width - 30, 400)
        p.drawOn(canvas, x_pos + 15, y_ori - tile_height + 10)

        text = []
        if issue.priority:
            text.append('Priority: {}'.format(issue.priority))

        try:
            estimate = int(issue.estimate)
        except TypeError:
            pass
        else:
            if 0 < estimate < 3600:
                text.append('Estimated: {}'.format(estimate / 60))
            else:
                text.append('Estimated: {}'.format(estimate // 3600))

        if text:
            p = Paragraph('<br/>'.join(text), style4)
            w, h = p.wrapOn(canvas, tile_width - 10, 400)
            p.drawOn(canvas, x_pos, y_ori - h - 5)

        y_pos = y_ori - tile_height - 50
        if not (i + 1) % 2:
            canvas.showPage()
            x_pos = page_width / 2 - tile_width / 2
            y_pos = page_height - 10

    canvas.save()


def parse_xml(filename, priority_field=None, custom_components=list()):
    issues = []
    tree = ET.parse(filename)
    root = tree.getroot()

    for item in root.find('channel').findall('item'):
        key = item.find('key').text
        summary = item.find('summary').text
        description = item.find('description').text
        reporter = item.find('reporter').text

        try:
            is_story = item.find('type').text == 'Story'
        except AttributeError:
            is_story = False

        if not is_story:
            continue

        components = [e.text for e in item.findall('component')]
        try:
            estimate = int(item.find('timeoriginalestimate').attrib['seconds'])
        except (AttributeError, ValueError):
            estimate = None
        try:
            assignee = item.find('assignee').text
        except AttributeError:
            assignee = None
        else:
            if assignee == 'Unassigned':
                assignee = None

        if priority_field:
            for e in item.find('customfields'):
                if e.attrib.get('id') == priority_field:
                    try:
                        priority = int(float(e.find('customfieldvalues').find('customfieldvalue').text))
                    except (AttributeError, ValueError):
                        priority = None
                    finally:
                        break
            else:
                priority = None
        else:
            priority = None

        # Rename components
        if custom_components:
            new_components = []
            for cmpt in components:
                for custom_cmpt in custom_components:
                    if custom_cmpt.get('pattern'):
                        pattern = r'{}'.format(custom_cmpt['pattern'])

                        if re.search(pattern, cmpt, re.I):
                            cmpt = custom_cmpt['name']
                            break

                new_components.append(cmpt)

            components = list(set(new_components))

        issues.append(Issue(key, summary, description, reporter,
                            components=components, estimate=estimate,
                            assignee=assignee, priority=priority))

    return issues


def main():
    parser = argparse.ArgumentParser(description='Generate a PDF of JIRA issues for an Agile board')
    parser.add_argument('-c', '--config', help='JSON configuration file')
    parser.add_argument('-x', '--xml', help='JIRA XML file')
    parser.add_argument('-s', '--server', help='JIRA server')
    parser.add_argument('-u', '--user', help='user')
    parser.add_argument('-p', '--passwd', help='password')
    parser.add_argument('--project', help='JIRA project')
    parser.add_argument('--version', help="Project's version (e.g. Sprint 91)", nargs='+')
    parser.add_argument('-o', '--output', help='output file', required=True)

    args = parser.parse_args()

    server = None
    user = None
    passwd = None
    project = None
    version = None
    priority_field = None
    custom_components = []

    if args.config:
        config = load_conf(args.config)
        server = config.get('server')
        user = config.get('user')
        passwd = config.get('password')
        project = config.get('project')
        version = config.get('fixVersion')
        priority_field = config.get('priorityField')

        # Groups are sorted by pattern length (descending order)
        custom_components = sorted(config.get('components', []), key=lambda x: len(x.get('pattern', '')), reverse=True)

    if args.server:
        server = args.server

    if args.user:
        user = args.user

    if args.passwd:
        passwd = args.passwd

    if args.project:
        project = args.project

    if args.version:
        # handles version with or without double quotes
        version = ' '.join(args.version).strip('"')

    if args.xml:
        issues = parse_xml(args.xml, priority_field=priority_field, custom_components=custom_components)
    else:
        if not server:
            server = _input('JIRA server URL: ')

        if not user:
            user = _input('user: ')

        if not passwd:
            print('Using a password on the command line interface can be insecure.')
            passwd = _input('Password (): ', hide=True)

        if not project:
            project = _input('Project (e.g. IBU): ')

        if not version:
            version = _input('Version (e.g. Sprint 91): ').strip('"')  # trim double quotes if user types them

        con = JIRAClient(server, user, passwd)
        issues = con.get(project, version,
                         priority_field=priority_field, custom_components=custom_components)

    # sort by component (asc) and priority (desc)
    issues.sort(key= lambda x: (x.components, -x.priority if x.priority is not None else 1000))
    gen_pdf(issues, args.output, components=custom_components)


if __name__ == '__main__':
    main()
