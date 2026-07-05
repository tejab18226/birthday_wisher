# Imports the datetime class directly from the datetime module — allows using datetime() and datetime.now() without the dt.datetime prefix
from datetime import datetime

# Imports the EmailMessage class from the email.message module — a higher-level alternative to raw RFC 2822 string formatting that allows setting email headers (From, To, Subject) and body content via clean dictionary-style access rather than manually constructing a formatted string with "\n\n"
from email.message import EmailMessage

# Imports the pandas library for reading the birthdays CSV file into a DataFrame and converting it into a dictionary for fast date-based lookups
import pandas

# Imports the random module — used to randomly select one of the three letter templates so each birthday recipient receives a varied message
import random

# Imports the smtplib module — Python's built-in standard library for sending email messages using the SMTP (Simple Mail Transfer Protocol)
import smtplib

# Imports the time module — used to introduce a delay between sending multiple birthday emails to avoid exceeding the mail server's rate limit
import time

# Imports the os module
import os

# Constants

# Defines the delay in seconds between each email when multiple people share the same birthday — prevents hitting Mailtrap's free plan rate limit of one email per second; increase this value if errors persist
EMAIL_SEND_DELAY_SECONDS = 10

# Defines the hostname of the SMTP mail server to connect to — using Mailtrap's sandbox server for safe email testing without delivering messages to real recipients
SMTP_HOST = "sandbox.smtp.mailtrap.io"

# Defines the SMTP port number for the mail server connection — port 587 is the standard SMTP submission port for STARTTLS-encrypted connections; upgraded to TLS via starttls() before credentials are sent
SMTP_PORT = 587

# Defines the SMTP authentication username provided by Mailtrap
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")

# Defines the SMTP authentication password provided by Mailtrap
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

# Defines the sender's email address displayed in the From field
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")

# Defines the total number of letter templates available in the letter_templates directory — used to set the upper bound of randint()
TOTAL_TEMPLATES = 3

# Defines the file path to the birthdays CSV data file
BIRTHDAYS_CSV_PATH = "./birthdays.csv"

# Defines the directory path containing the letter template text files
TEMPLATES_DIR = "letter_templates"

# Defines the placeholder string in letter templates replaced with the birthday person's actual name during personalization
NAME_PLACEHOLDER = "[NAME]"


# Birthday Data Loading

def load_birthdays(csv_path: str) -> dict:
    """
    Reads the birthdays CSV file and returns a dictionary mapping (month, day) tuples to a list of all birthday person data rows sharing that date.

    Reads the CSV using pandas into a DataFrame, then builds the dictionary by iterating over every row — if a (month, day) key already exists the
    new row is appended to the existing list, otherwise a new list is created for that key; this ensures all people sharing the same birthday date are collected and every one of them receives a birthday email.

    Args:
        csv_path (str): The file path to the birthdays CSV file containing "name", "email", "month", and "day" columns.

    Returns:
        dict: A dictionary mapping (month, day) tuples to a list of pandas Series rows for all people with that birthday — e.g. {(12, 15): [Series(Alice), Series(Bob)]}. Returns an empty dictionary if the file is not found.
    """
    # Attempts to read and convert the CSV file
    try:

        # Reads the birthdays CSV into a pandas DataFrame
        data = pandas.read_csv(csv_path)

        # Initializes an empty dictionary to store (month, day) → [rows] mapping
        birthdays_dict: dict = {}

        # Iterates over every row in the DataFrame to build the grouped dictionary
        for index, data_row in data.iterrows():

            # Builds the (month, day) tuple key from the current row's date values
            birthday_key = (data_row["month"], data_row["day"])

            # Checks if this (month, day) key already exists in the dictionary — True means at least one other person shares this birthday date
            if birthday_key in birthdays_dict:

                # Appends the current row to the existing list for this date — preserves all previously stored people sharing this birthday
                birthdays_dict[birthday_key].append(data_row)

            # Executes when this (month, day) key is seen for the first time
            else:

                # Creates a new list with the current row as the first entry for this birthday date key
                birthdays_dict[birthday_key] = [data_row]

        return birthdays_dict

    # Catches FileNotFoundError raised if the CSV file does not exist
    except FileNotFoundError:
        print(f"Birthdays data file not found at '{csv_path}' — please ensure the file exists before running.")
        return {}

    # Catches any other unexpected exception during CSV reading
    except Exception as e:
        print(f"An unexpected error occurred while loading the birthdays file: {e}")
        return {}


def load_letter_template(templates_dir: str, total_templates: int) -> str | None:
    """
    Randomly selects and reads one of the available letter template files, returning its content as a string.

    Generates a random integer between 1 and total_templates to select a template file, opens and reads its full content, and returns the raw template string with the [NAME] placeholder still intact for replacement.

    Args:
        templates_dir (str): The directory path containing the letter templates.
        total_templates (int): The total number of available template files.

    Returns:
        str | None: The full content of the randomly selected template file as a string, or None if the file could not be read.
    """
    # Builds the file path using a random integer between 1 and total_templates
    file_path = f"{templates_dir}/letter_{random.randint(1, total_templates)}.txt"

    # Attempts to open and read the randomly selected template file
    try:

        # Opens the template file in default read mode
        with open(file_path) as letter_file:

            # Reads and returns the entire template content as a single string
            return letter_file.read()

    # Catches FileNotFoundError raised if the selected template does not exist
    except FileNotFoundError:

        # Prints an error message identifying the missing template file
        print(f"Birthday letter template not found at '{file_path}' — please ensure all {total_templates} templates exist in '{templates_dir}'.")
        return None

    # Catches any other unexpected exception during template reading
    except Exception as e:

        # Prints the unexpected error details for diagnosis
        print(f"An unexpected error occurred while reading the letter template: {e}")
        return None


def send_birthday_email(birthday_person: pandas.Series, letter_content: str, today: datetime) -> None:
    """
    Constructs and sends a personalized birthday email to the birthday person.

    Builds an EmailMessage object with the From, To, and Subject headers and the personalized letter content as the plain text body, then opens a STARTTLS-encrypted SMTP connection, authenticates, and transmits the email.

    Args:
        birthday_person (pandas.Series): The row Series from the birthdays DataFrame containing "name" and "email".
        letter_content (str): The personalized letter text with [NAME] already replaced by the birthday person's actual name.
        today (datetime): The current datetime object used for the confirmation message timestamp.

    Returns:
        None
    """
    # Attempts to construct and send the birthday email via SMTP
    try:

        # Creates a new EmailMessage object for clean header and body assignment
        msg = EmailMessage()

        # Sets the From header to the defined sender address
        msg["From"] = SENDER_EMAIL

        # Sets the To header to the birthday person's email from the CSV data
        msg["To"] = birthday_person["email"]

        # Sets the Subject header with a personalized birthday greeting
        msg["Subject"] = f"Happy Birthday, {birthday_person['name']}! 🎂"

        # Sets the plain text body to the personalized letter content
        msg.set_content(letter_content)

        # Opens an SMTP connection using the with keyword — automatically calls quit() when the block exits regardless of success or exception
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as connection:

            # Upgrades the plain connection to TLS encryption before transmitting any credentials or email content
            connection.starttls()

            # Authenticates with the mail server using the defined credentials
            connection.login(SMTP_USERNAME, SMTP_PASSWORD)

            # Transmits the EmailMessage object to the mail server — send_message() automatically extracts all headers from the EmailMessage object, cleaner than the lower-level sendmail()
            connection.send_message(msg)

        # Prints a professional confirmation message after successful delivery
        print(f"Birthday email successfully sent to {birthday_person['name']} at {birthday_person['email']} on {today.strftime('%Y-%m-%d')}.")

    # Catches any exception raised during email construction or SMTP sending
    except Exception as e:

        # Prints the specific error details for diagnosis
        print(f"Failed to send birthday email to {birthday_person['name']} at {birthday_person['email']} — the following error occurred: {e}")


# Main Birthday Check and Email Flow

def main() -> None:
    """
    Main entry point for the birthday email automation program.

    Loads the current date, retrieves all birthday entries from the CSV file, checks if today matches any stored birthday, and sends a personalized
    birthday email to EVERY person whose birthday falls on today's date — correctly handling multiple people sharing the same birthday by iterating over the full list of matching recipients.

    Returns:
        None
    """
    # Creates a datetime object representing the current local date and time
    today = datetime.now()

    # Creates a (month, day) tuple from the current date — year excluded so birthdays match every year regardless of the current year
    today_tuple = (today.month, today.day)

    # Prints the current date being checked for development verification
    print(f"Checking birthdays for: {today.strftime('%B %d')} ({today_tuple})")

    # Loads all birthday entries grouped by (month, day) into the dictionary
    birthdays_dict = load_birthdays(BIRTHDAYS_CSV_PATH)

    # Exits early if no birthday data was loaded
    if not birthdays_dict:
        print("No birthday data available — please check the birthdays CSV file and try again.")
        return

    # Checks if today's (month, day) tuple exists as a key in the dictionary
    if today_tuple in birthdays_dict:

        # Retrieves the LIST of all people with a birthday today — may contain one or more people sharing the same birthday date
        birthday_people = birthdays_dict[today_tuple]

        # Prints how many people have a birthday today
        print(f"{len(birthday_people)} birthday(s) found for today ({today.strftime('%B %d, %Y')}).")

        # Iterates over every person in the birthday list — ensures every person sharing today's birthday receives their own personalized email
        for index, birthday_person in enumerate(birthday_people):

            # Prints the current recipient being processed
            print(f"Sending birthday email to {birthday_person['name']} ({birthday_person['email']}).")

            # Loads a randomly selected letter template for this person — each person gets a independently random template selection
            letter_content = load_letter_template(TEMPLATES_DIR, TOTAL_TEMPLATES)

            # Proceeds only if a valid template was successfully loaded
            if letter_content:

                # Replaces the [NAME] placeholder with this person's actual name
                personalized_content = letter_content.replace(NAME_PLACEHOLDER,birthday_person["name"])

                # Sends the personalized birthday email to this specific person
                send_birthday_email(birthday_person, personalized_content, today)

                # Adds a delay between emails when more people remain to be sent — prevents hitting the mail server's rate limit (too many emails per second) on free plans; skips the delay after the last email since no further emails need to be sent in this session
                if index < len(birthday_people) - 1:
                    # Prints an informational message showing the delay being applied
                    print(
                        f"Waiting {EMAIL_SEND_DELAY_SECONDS} second(s) before sending the next email to avoid rate limiting...")

                    # Pauses execution for the defined delay duration before the next iteration sends the following birthday email
                    time.sleep(EMAIL_SEND_DELAY_SECONDS)


    # Executes when no birthday entry matches today's date
    else:

        # Prints an informational message confirming no birthdays today
        print(f"No birthdays found for today ({today.strftime('%B %d, %Y')}) — no email sent.")


# Calls the main function to start the birthday email automation program
main()