"""Script for parsing emails. By default finds all ips (v4 and v6) and domains in letter,
writes it into db and prints it in console. Can also search headers by pattern or substring
(start script with parameters -hs --header-string to search by string, and -hp --header-pattern
to use regex pattern).
Writes logs into main.log. It's possible to change level of logging (by adding -cl
--change-level argument)."""


import re
import json
import sys
import argparse
import logging
import mysql.connector

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                    filename='main.log')
LOGGER = logging.getLogger()
DB_CONF_FILE = 'db_conf.json'
LEVELS = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO,  'WARNING': logging.WARNING,
          'ERROR': logging.ERROR,  'CRITICAL': logging.CRITICAL}


class DbConnection:
    """Class, based on singleton pattern for creating database connection instance.
    Uses MySQL connector."""

    _instance = None

    def __new__(cls, *ars, **kwars):
        """Singleton pattern realization"""

        if not isinstance(cls._instance, DbConnection):
            cls._instance = object.__new__(cls)
        return cls._instance

    def __init__(self, host='127.0.0.1', port=3306, user='root', password='', data_base=''):
        """Initializes a class and creates db connection instance.

        :param host: MySQL server host
        :param port: MySQL server port
        :param user: username of user with needed privileges
        :param password: user's password
        :param data_base: name of already created schema
        """

        self.host = host
        self.port = port
        self.user = user

        if password != '':
            self.password = password
        else:
            logging.error('Password could not be an empty string. Check db configuration.')
            sys.exit(2)

        if data_base != '':
            self.data_base = data_base
        else:
            logging.error('You have to select database to connect to. Check db configuration.')
            sys.exit(2)

        try:
            self.conn = mysql.connector.connect(host=self.host, database=self.data_base,
                                                user=self.user, password=self.password,
                                                port=self.port)
            if self.conn.is_connected():
                logging.info("Database connected.")
                self.recreate_tables()
            else:
                logging.info("Connection failed.")
                self.conn = None
        except mysql.connector.Error:
            logging.info("Can not connect to database!")
            self.conn = None

    def recreate_tables(self):
        """Method for cleaning database. It drops old tables and creates new empty
        tables 'ips' and 'domains"""

        cursor = self.conn.cursor()

        try:
            cursor.execute("DROP TABLE ips")
            logging.debug("Old table ips dropped")
        except mysql.connector.errors.ProgrammingError:
            pass
        finally:
            cursor.execute("CREATE TABLE ips (id INT PRIMARY KEY AUTO_INCREMENT UNIQUE, ip "
                           "VARCHAR(255) NOT NULL)")
            logging.info("Table ips created")
        try:
            cursor.execute("DROP TABLE domains")
            logging.debug("Old table domains dropped")
        except mysql.connector.errors.ProgrammingError:
            pass
        finally:
            cursor.execute(
                "CREATE TABLE domains (id INT PRIMARY KEY AUTO_INCREMENT UNIQUE, "
                "domain VARCHAR(255) NOT NULL)")
            logging.info("Table domains created")


def start_db_connection():
    """Function for loading db configuration json file and create DbConnection instance.
    :returns DbConnection instance"""

    try:
        db_conf = json.load(open(DB_CONF_FILE))
        logging.debug("Db configuration loaded")
    except FileNotFoundError:
        logging.error('DB configuration file not found')
        sys.exit(2)
    db_instance = DbConnection(host=db_conf['host'], data_base=db_conf['db'],
                               user=db_conf['user'], password=db_conf['password'],
                               port=db_conf['port'])
    logging.debug("DbConnection instance created")
    if not db_instance.conn:
        logging.error('DB connection failed. Check configuration file and db server status.')
        sys.exit(2)

    return db_instance


def open_mail(path_to_mail: str):
    """
    Function to correctly open and read email file. If there are some problems with file
    (wrong extension, file not found) func logs message and exits

    :param path_to_mail: path to email file (str) with extension .eml
    :return: content of email (str)
    """

    if not isinstance(path_to_mail, str):
        logging.error('Wrong datatype input. Path to mail have to be string')
        sys.exit(2)

    if path_to_mail.find('.eml') == -1:
        logging.error('File has wrong extension. You have to choose \".eml\" file.')
        sys.exit(2)

    try:
        with open(path_to_mail, 'r') as file:
            file_text = file.read()
            logging.debug("Email file opened")
    except FileNotFoundError:
        logging.error('File not found. Check your path or choose another file. Entered path: %s'
                      % path_to_mail)
        sys.exit(2)
    return file_text


def tld_config():
    """Func loads TLD configuration file and makes a regex pattern from all domains from it
    :returns regex pattern of TLD"""

    try:
        tld_list = open('TLD.conf').read()
    except FileNotFoundError:
        logging.info('No TLD config found. Setting a default TLD configuration...')
        tld_list = 'com|org|net|int|edu|gov|mil|arpa'
    last_n = tld_list.rfind('\n')
    if len(tld_list) - last_n == 1:
        tld_list = tld_list[:last_n]
    tld_list = tld_list.replace('\n', '|')
    return tld_list


def parse_mail(email_content: str, db_conn: DbConnection):
    """
    Function parses email text to find IPs (v4  and v6) and domains, and writes it into db.

    :param db_conn: MySQL db connection
    :param email_content: text content of email (str)
    """

    if not isinstance(email_content, str):
        logging.debug('Email content variable should be a string.')
        logging.error('Email content has incorrect type')
        sys.exit(2)

    ip_v4 = re.findall(r"(?<!\w|\.)(\d{1,3}(?:\.\d{1,3}){3})(?!\.?\w)",
                       email_content)
    ip_v6 = re.findall(r"(?<!\w|\.)([\dA-Fa-f]{0,4}(?::[\dA-Fa-f]{0,4}){4,8}(?!\.?\w))",
                       email_content)
    doms = re.findall(r"(?<!\w|\.)([\w\-]+(?:\.\w+)*(?:\.(?:" + tld_config() + r")))(?!\.?\w)",
                      email_content)

    cursor = db_conn.conn.cursor()
    for ip_4 in ip_v4:
        cursor.execute("INSERT INTO ips(ip) VALUES (\"%s\")" % ip_4)
        logging.info('Ip added to db: %s' % ip_4)
    for ip_6 in ip_v6:
        cursor.execute("INSERT INTO ips(ip) VALUES (\"%s\")" % ip_6)
        logging.info('Ip added to db: %s' % ip_6)
    for dom in doms:
        cursor.execute("INSERT INTO domains(domain) VALUES (\"%s\")" % dom)
        logging.info('Ip added to db: %s' % dom)
    db_conn.conn.commit()


def get_ips_and_domains(db_conn: DbConnection):
    """Function selects all IPs (v4  and v6) and domains from db, and prints it to console.

    :param db_conn: MySQL db connection"""

    cursor = db_conn.conn.cursor()
    cursor.execute("SELECT ip, COUNT(ip) FROM ips GROUP BY ip ORDER BY COUNT(ip) DESC")
    rows = cursor.fetchall()
    logging.info('Selected %d rows from table \'ips\'' % cursor.rowcount)
    print('\nIPs:')
    try:
        if rows[0][1] != 1:
            for row in rows:
                print(row[0], "\t", row[1])
        else:
            for row in rows:
                print(row[0])
    except IndexError:
        print("No ips in database")

    cursor.execute("SELECT domain, COUNT(domain) FROM domains GROUP BY "
                   "domain ORDER BY COUNT(domain) DESC")
    rows = cursor.fetchall()
    logging.info('Selected %d rows from table \'domains\'' % cursor.rowcount)
    print('\nDomains:')
    try:
        if rows[0][1] != 1:
            for row in rows:
                print(row[0], "\t", row[1])
    except KeyError:
        print("No domains in database")


def get_header(email_content: str):
    """Function parses email text to slice it's header.

    :param email_content: text content of email (str)
    :returns head of email with it's headers (str)"""

    header_endpoint = email_content.find('<!DOCTYPE html')
    head = email_content[:header_endpoint]
    logging.debug('Email header sliced')
    return head


def header_search(email_content: str, substring='', pattern=''):
    """Function parses email text to find IPs (v4  and v6) and domains, and writes it into db.

    :param email_content: text content of email (str)
    :param pattern: (str) regex patter entered by user (default empty string)
    :param substring: (str) searched substring entered by user (default empty string)
    :returns list of all found headers
    """

    if not isinstance(email_content, str):
        logging.debug('Email content variable should be a string.')
        logging.error('Email content has incorrect type')
        sys.exit(2)

    head = get_header(email_content)
    if pattern == '' and substring != '':
        pattern = '.*' + substring + r'.*'
    elif pattern != '' and substring == '':
        pass
    else:
        logging.error('It could be only one type of search: pattern or substring')
        sys.exit(2)

    substrs = re.findall(pattern, head)
    logging.info('Found %d headers which contains %s pattern' % (len(substrs), pattern))
    return substrs


if __name__ == '__main__':

    logging.info('\n\nProgram started\n')

    parser = argparse.ArgumentParser()
    parser.add_argument("-cl", "--change-level", help="Change level of logging. Default: DEBUG",
                        action="store", type=str, dest="logging_level", default='')
    parser.add_argument("-hp", "--header-pattern", help="Search header with pattern",
                        action="store", type=str, dest="pattern")
    parser.add_argument("-hs", "--header-string", help="Search header with substring",
                        action="store", type=str, dest="substring")
    parser.add_argument("-e", "--email", help="Path to email file with .eml extension",
                        action="store", type=str, dest="mail_path", required=True)

    args = parser.parse_args()

    log_level = args.logging_level.upper()
    if log_level in LEVELS.keys():
        logging.info('\n\nLevel changed to %s\n' % log_level)
        LOGGER.setLevel(LEVELS[log_level])

    db_connection = start_db_connection()
    mail_text = open_mail(args.mail_path)
    parse_mail(mail_text, db_connection)

    SEARCH_RESULTS = None
    if args.pattern:
        SEARCH_RESULTS = header_search(mail_text, pattern=args.pattern)
    elif args.substring:
        SEARCH_RESULTS = header_search(mail_text, substring=args.substring)

    if SEARCH_RESULTS:
        print('\nSearch results:')
        for header in SEARCH_RESULTS:
            print(header)

    get_ips_and_domains(db_connection)
    logging.info('\nProgram ended\n')
