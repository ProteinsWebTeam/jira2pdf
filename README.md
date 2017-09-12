# JIRA2PDF

JIRA2PDF generates a PDF file of JIRA user stories for your agile wallboard.
 
## Requirements

Python 3 with the `reportlab` module.

## Usage

```
Usage: jira2pdf.py [options] -o output.pdf

Generate a PDF of JIRA issues for an Agile board

required arguments:
  -o OUTPUT, --output OUTPUT        output file

optional arguments:
  -h, --help                        show this help message and exit
  -c CONFIG, --config CONFIG        JSON configuration file
  -x XML, --xml XML                 JIRA XML file
  -s SERVER, --server SERVER        JIRA server
  -u USER, --user USER              user
  -p PASSWD, --passwd PASSWD        password
  --project PROJECT                 JIRA project
  --version VERSION                 Project's version (e.g. Sprint 91)
```

The arguments required to use the JIRA API can be defined in the config JSON file (`-c, --config`) instead of being passed on the command line. If they are neither defined in the config JSON file nor on the command line, a prompt is displayed when running the script. As it is insecure to store and use passwords in plain text, it is recommended to leave the script displays at least the password prompt (your password will not be displayed).

### Getting user stories

There are two ways to retrieve user stories to be printed. 

#### JIRA Cloud REST API

You can download stories for a given project and fix version from the JIRA Cloud REST API by providing your JIRA credentials, and the server URI.

#### XML

Alternatively, you can export issues from JIRA in the XML format, and pass the XML file to JIRA2PDF with the `-x, --xml` parameter.

Please note that the project and the fix version are not considered in this mode: it is left to the user to properly filter issues before exporting them.

### Properties

The following properties can be defined in the config JSON file.

| Name              | Description  |
| ----------------- | ------------ |
| `server`        | The JIRA server URI |
| `user`          | Username |
| `password`      | Password *(storing passwords in plain text is insecure)* |
| `project`       | Project key (first part of the project's issue keys) |
| `fixVersion`    | Fix version of the issues |
| `priorityField` | Custom field used to assign a priority code to an issue | 
| `components`    | List of user-defined components. See [Components](#components) | 

#### Example

```json
{
  "server": "https://www.ebi.ac.uk/panda/jira",
  "user": "mblum",
  "password": "",
  "project": "IBU",
  "fixVersion": "Sprint 93",
  "priorityField": "customfield_10131",
  "components": [
    {
      "name": "InterPro",
      "pattern": ".*InterPro.*",
      "color": "#9b59b6"
    },
    {
      "name": "InterPro Web",
      "pattern": ".*InterPro Web.*",
      "color": "#3498db"
    },
    {
      "name": "HMMER",
      "pattern": "HMMER.*",
      "color": "#e74c3c"
    },
    {
      "name": "Pfam",
      "pattern": "Pfam.*",
      "color": "#074987"
    },
    {
      "name": "EMG",
      "pattern": "EMG.*",
      "color": "#2ecc71",
      "exclude": true
    }
  ]
}
```

### Components

The first ten components are assigned a different colour (following components are assigned a default colour), thus cards are coloured with respect to the issue's component.

It is possible to assign the same colour to multiple components by using the `components` property in the config JSON file.

| Name              | Description  |
| ----------------- | ------------ |
| `name`            | Meta-component name (e.g. "Web dev") |
| `pattern`         | Regular expression to capture components (e.g. "Web.*") |
| `color`           | Colour in the hexadecimal format (e.g. #008080) |
| `exclude`         | Skip this component's issues |
