#!/usr/bin/env python
"""
Copyright 2014, BlinkMobile
"""
import argparse
import time
import sys
import re
import os
import tempfile
import simplejson
import boto.s3
import boto.ses

def main():
    """
    This is designed to take MIME emails stored in S3, 
    and sends a new email with a signed URL to that email file. 
    We use this when we store emails that are over  10MB 
    (that SES won't send). 
    """
    args = argparse.ArgumentParser()
    args.add_argument('--bucket', '-b',
                      help='Bucket Name (e.g. "blinkmobile-logs")',
                      required=True)
    args.add_argument('--prefix', '-p', help='S3 prefix to emails that'
                      'should be processed (e.g. "emails")',
                      required=True)
    args.add_argument('--region', '-r', help='AWS region (e.g. "us-west-1")',
                      required=True)
    args.add_argument('--processedEmails', '-e',
                      help='S3 prefix to processed emails JSON file '
                           '(e.g. emails/_PROCESSING/processedEmails.json)',
                      required=True)
    args.add_argument('--adminEmail', '-a',
                      help='An SES Verified Email Address to send statistics '
                           'to after completion (e.g. admin@admin.com)',
                      required=False)
    options = args.parse_args()

    bucket_name = options.bucket
    bucket_prefix = options.prefix
    bucket_region = options.region
    bucket_processed_emails = options.processedEmails
    administrator_email = options.adminEmail
    
    if not administrator_email:
        print "WARNING: No Administrator Email given, " \
              "email summary of statistics disabled"

    email_to = ""
    email_from = ""
    email_cc = ""
    email_subject = ""
    email_date = ""
    email_rt = email_from
    emails_sent = 0
    todays_date = time.strftime("%d-%m-%Y")

    processed_emails_temp = tempfile.NamedTemporaryFile(delete=False)
    processed_emails_file_path = processed_emails_temp.name

    message_location_temp = tempfile.NamedTemporaryFile(delete=False)
    message_location = message_location_temp.name

    ####
    # Main function begins:
    ####
    print 'Connecting to S3 + SES via Boto...'
    conn = boto.connect_s3()
    ses_connection = boto.ses.connect_to_region(bucket_region)
    print 'Connected.'

    bucket = conn.get_bucket(bucket_name, validate=False)

    ####
    # Preparing Processed Emails JSON File (which returns a python dictionary)
    ####
    processed_emails = prepare_json(
        bucket, bucket_processed_emails, processed_emails_file_path)

    # prefix must end it in 'msg' if accessing subfolders
    for key in bucket.list(prefix=bucket_prefix):
        add_to_dict = False
        key = bucket.get_key(key.name)
        kn = key.name

        # print key.name
        # print key.size
        key_in_mb = ((key.size / 1024) / 1024)
        # print "Size (in MB): %s" % key_in_mb
        if key_in_mb >= 10:
            print key.name
            print "Size (in MB): %s" % key_in_mb
            # check against python dict
            # if not in it, add and progress
            if key.name in processed_emails:
                add_to_dict = False
            else:
                add_to_dict = True

            if add_to_dict:
                ####
                # Generating Signed URL
                ####
                signed_url = get_signed_url(key)
                ####
                # Downloading Email to Disk (inside /tmp/)
                ####
                print "Downloading file"
                key.get_contents_to_filename(message_location)
                print "File downloaded. Opening"

                # clearing email_cc + email_rt as they're optional.
                email_to = ""
                email_from = ""
                email_cc = ""
                email_rt = ""
                email_subject = ""
                email_date = ""
                with open(message_location) as key_file:
                    for line in key_file:
                        if re.match("(To):(.*)", line):
                            temp = line
                            temp_to = temp.replace("To: ", "").replace("\n", "").lstrip(' ')
                            email_to = temp_to.split(",")

                            # sometimes 'to' addresses are split over
                            # multiple lines.
                            next_line = key_file.next()
                            # print next_line
                            # and sometimes it doesn't, meaning the Subject
                            # is on the next line:
                            if re.match("(Subject):(.*)", next_line):
                                temp = next_line
                                email_subject = temp.replace(
                                "Subject: ", "").replace("\n", "")
                            elif re.match("(.*)@(.*)", next_line):
                                temp2 = next_line.replace("\n", "").lstrip(' ')
                                temp2_to = temp2.split(",")
                                unfiltered_email_to = email_to + temp2_to
                                email_to = filter(None, unfiltered_email_to)

                        if re.match("(.*)(From):(.*)", line):
                            temp = line
                            email_from = temp.replace("From: ", "").replace(
                                "\n", "")
                        if re.match("(.*)(Cc):(.*)", line):
                            temp = line
                            temp_cc = temp.replace("Cc: ", "").replace(
                                "\n", "")
                            email_cc = temp_cc.split(",")

                            # sometimes 'cc' addresses are split over
                            # multiple lines.
                            next_line = key_file.next()
                            # and sometimes it isn't, meaning the Reply-To
                            # is on the next line
                            if re.match("(.*)(Reply-To):(.*)", next_line):
                                temp = next_line
                                temp_rt = temp.replace("Reply-To: ", "") \
                                    .replace("\n", "")
                                email_rt = temp_rt.split(",")
                            elif re.match("(.*)@(.*)", next_line):
                                temp2 = next_line.replace("\n", "").lstrip(
                                    ' ')
                                temp2_cc = temp2.split(",")
                                unfiltered_email_cc = email_cc + temp2_cc
                                email_cc = filter(None, unfiltered_email_cc)

                        if re.match("(.*)(Reply-To):(.*)", line):
                            temp = line
                            temp_rt = temp.replace("Reply-To: ", "")\
                                .replace("\n", "")
                            email_rt = temp_rt.split(",")

                        if re.match("(.*)(Subject):(.*)", line):
                            temp = line
                            email_subject = temp.replace(
                                "Subject: ", "").replace("\n", "")

                        if re.match("(.*)(Date):(.*)", line):
                            temp = line
                            email_date = temp.replace("Date: ", "").replace(
                                "\n", "")

                # if email isn't in dictionary, then it hasn't been sent yet
                # therefore add to dictionary and send it.

                print "adding to dictionary"
                processed_emails.update({
                    key.name: {
                        'date': email_date,
                        'emailSent': todays_date,
                        'email': [{
                            'from': email_from,
                            'to': email_to,
                            'subject': email_subject
                        }]
                    }})

                send_email(
                    ses_connection, signed_url, email_from, email_subject,
                    email_to, email_cc, email_rt, email_date)
                emails_sent += 1
                print "-----"

    ####
    # convert python dictionary back to JSON, upload JSON
    ####
    print "Processing Dictionary"
    process_dictionary(
        bucket,
        bucket_processed_emails,
        processed_emails_file_path,
        processed_emails)
    ####
    # delete temp files from machine
    #####
    print "Deleting Temporary Files"
    delete_temp_files(message_location, processed_emails_file_path)

    if administrator_email:
        print "Sending Statistics to: %s" % administrator_email
        send_stats(
            ses_connection, emails_sent, processed_emails, administrator_email)


def send_stats(ses_connection, emails_sent, processed_emails, email_address):
    """ As this is designed to be run automatically on a timer,
    this will compile an email with statistics (e.g. how many emails were
    sent, biggest size, etc) to be sent to someone once execution is complete.
    :return: Null.
    """
    date = time.strftime("%d-%m-%Y")
    pe_counter = len(processed_emails)
    body = "Hi,\n\SES Woomera just finished. Here" \
           "are some stats from the execution:"\
           "\n\n" \
           "Today's Date: %s\n"\
           "Emails sent: %s\n" \
           "Emails in 'Processed Emails' JSON File: %s\n " \
           % (date, emails_sent, pe_counter)

    ses_connection.send_email(
        source=email_address,
        subject="[SES Woomera] Email Statistics -- %s" % date,
        to_addresses=email_address,
        body=body,
        format="text")


def delete_temp_files(message_location, processed_emails_file_path):
    """
    This deletes temporary files that get accumulated during the process
    Including the ProcessedEmails JSON file, and any emails that need to be
    sent.
    :return: Null
    """
    os.remove(message_location)
    os.remove(processed_emails_file_path)


def prepare_json(bucket, bucket_processed_emails, processed_emails_file_path):
    """
    downloads the processed emails JSON file (which keeps track of emails
    that have already been processed/sent).

    In addition, it converts the JSON file to a Python Dictionary, which
    makes processing easier.

    :return: processed_emails_dict: a python dictionary of the
    JSON file downloaded from S3.
    """

    key = boto.s3.key.Key(bucket=bucket,
                          name=bucket_processed_emails)
    # if the key (json file) exists, download it from s3
    # if it doesn't, create a new file in preparation to upload to S3.
    if key.exists():
        key.get_contents_to_filename(processed_emails_file_path)
    else:
        # creating file
        open(processed_emails_file_path, 'a').close()

    # convert to python dict
    # print processed_emails_file_path
    # f = open(processed_emails_file_path, 'r')
    # print f.read()
    processed_emails_json = open(processed_emails_file_path).read()
    processed_emails_dict = {}
    try:
        processed_emails_dict = simplejson.loads(processed_emails_json)
        print "Processed Emails Dictionary: %s" % processed_emails_dict
    # this mostly occurs when the file is empty
    except simplejson.scanner.JSONDecodeError:
        print ""

    return processed_emails_dict


def get_signed_url(key):
    """
    :param key: refers to the file inside S3 that requires a signed URL
    :return signedURL: a signed URL
    """

    signed_url = key.generate_url(
        1209600,  # 14 days
        method='GET',
        query_auth=True,
        force_http=False,
        response_headers={
            'response-content-type': 'binary/octet-stream'
        })
    return signed_url


def send_email(ses_connection, signed_url, email_from, email_subject, email_to,
               email_cc, email_rt, email_date):
    """
    Function designed to send an email
    :param signed_url: The Signed URL
    :param email_from: The "from" email address
    :param email_subject: The Subject of the email
    :param email_to: The "to" email address
    :param email_cc: The "cc" email address/es
    :param email_rt: the "Reply-To" email addresses.
    :param email_date: The date that the original email was sent.
    :return: Null.
    """

    # print "Setting up email Body"
    email_body = "Hi,\n\nThe Blink Mobility Platform attempted to " \
                 "process this email (Sent: %s), however the email size " \
                 "(including attachments) " \
                 "exceeded the 10MB limit.\n\n" \
                 "To access the email, please click the following link " \
                 "(which will expire in 14 days): \n\n" \
                 "%s" \
                 "\n\n" \
                 "Opening Instructions:\n\n " \
                 "1. Download the file\n " \
                 "2. Open the file in your chosen mail client " \
                 "(e.g. Apple Mail, Microsoft Outlook, etc)\n " \
                 "3. The email should open displaying the " \
                 "email body and all attachments \n\n " \
                 "Thanks,\n " \
                 "BlinkMobile Interactive" % (email_date, signed_url)

    # print emailBody
    print "SENDING EMAIL -- From: %s To: %s CC: %s Subject: %s" \
          % (email_from, email_to, email_cc, email_subject)
    ses_connection.send_email(
        source=email_from,
        subject=email_subject,
        body=email_body,
        to_addresses=email_to,
        cc_addresses=email_cc,
        reply_addresses=email_rt
    )


def process_dictionary(bucket, bucket_processed_emails,
                       processed_emails_file_path, processed_emails_dict):
    """
    Once emails have been sent, the processed emails dictionary gets
    converted back into a JSON file and it gets uploaded to S3.

    :param processed_emails_dict: the Python dictionary containing all
    processed emails (that needs to be converted to a JSON file)
    :return: Null.
    """
    # converting from dict to json
    pe_json = simplejson.dumps(processed_emails_dict)

    # writing to json file
    pe_file = open(processed_emails_file_path, 'w')
    pe_file.write(pe_json)
    pe_file.close()

    # Upload to S3
    # print "uploading to s3"
    k = bucket.new_key(bucket_processed_emails)
    k.set_contents_from_filename(processed_emails_file_path)


if __name__ == '__main__':
    main()

