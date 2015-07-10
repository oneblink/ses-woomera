# SES Woomera

Notify intended recipients that AWS's Simple Email Service attempted to send an email to them, but the email exceeded SES's size limits and instead offering recipients a way to recover the email.

----
 
## Our Problem:
- We use Sendmail on Amazon Linux EC2 Instances, which communicates to Amazon's Simple Email Service (SES) to send emails.
- SES has a hard limit of 10MB. If we try to send any emails over 10MB, SES refuses to send it.
- Emails then get lost, floating in limbo between SES and our instances with no way to recover it.
- That's where this comes in...

## What does it do?
Before we progress, some legwork has to be implemented before this can work. Including:

- A way to archive emails that sendmail sends to SES
   - We used ['copymail.m4'](http://serverfault.com/questions/229029/configuring-sendmail-to-archive-a-copy-of-any-outgoing-message), taken from [alvosu](http://serverfault.com/users/68346/alvosu) at [serverfault.com](https://serverfault.com)
- A way to store those emails in S3
  - We used logrotate + a script utilising formail based off an [answer on StackOverflow](http://stackoverflow.com/questions/11281893/how-to-split-mailbox-into-single-file-per-message) from [Igor Chubin](http://stackoverflow.com/users/1458569/igor-chubin)

Once you've got emails split into multiple files and stored in S3, this script does the following:
  - Scans S3 and finds emails over 10MB (which wouldn't have been sent due to SES's 10MB limit)
  - If it finds anything, it generates a signed URL to that file and extracts key information from the email (incl. To/From/CC/Reply-To/Subject)
  - Sends a *new* email to the intended recipients, stating that their message has been stored in S3 temporarily, and to download it using the signed URL.
  - Once execution is complete, sends an email to a predetermined address with statistics (emails sent, etc). This is optional.

In addition to the script, this repository contains a Data Pipeline Definition, which can automate the process.

**The Data Pipeline (data-pipeline/):**

Contains a Data Pipeline Definition (pipeline-definition.json.default) which
- Downloads and runs a Bash Script (ses-woomera-pipeline.sh) which...
- Downloads and runs the Python Script (ses-woomera.py)

## How to use it:
**Prerequesites:**
- [An AWS Account](http://aws.amazon.com/getting-started/)
- [AWS CLI Installed](http://aws.amazon.com/cli/)
- Python (Written using Python 2.7.8)

**The Script:**

```
usage: ses-woomera.py [-h] --bucket BUCKET --prefix PREFIX --region REGION --processedEmails PROCESSEDEMAILS --accessKey ACCESSKEY --secretKey SECRETKEY --adminEmail ADMINEMAIL
     
arguments:
  -h, --help            show this help message and exit
  --bucket BUCKET, -b BUCKET
                        Bucket Name (e.g. "blinkmobile-logs")
  --prefix PREFIX, -p PREFIX
                        S3 prefix to emails thatshould be processed (e.g. "emails")
  --region REGION, -r REGION
                        AWS region (e.g. "us-west-1")
  --processedEmails PROCESSEDEMAILS, -e PROCESSEDEMAILS
                        S3 prefix to processed emails JSON file (e.g.emails/_PROCESSING/processedEmails.json)
  --accessKey ACCESSKEY, -k ACCESSKEY
                        The AWS Access Key in the Access/Secret Keypair
  --secretKey SECRETKEY, -s SECRETKEY
                        The AWS Secret Key in the Access/Secret Keypair
  --adminEmail ADMINEMAIL, -a ADMINEMAIL
                        (OPTIONAL) An SES Verified Email Address to send statistics to after completion 
                        (e.g.admin@admin.com)
```

- Example: ```python ses-woomera.py -b blinkmobile-emails -p 2015/msg -r us-east-1 -e 2015/processed-emails.json -k AKIABCDEFGHIJKL -s AJFJ4+FGNHSDJT56IWCNZ/AUQKSOIH -a email@email.com ```

**The Pipeline:**
- Create a new Pipeline in AWS
- Import the JSON Definition located at data-pipeline/pipeline-definition.json.default
- Change Variables (anything marked with ```${TEXT}```)
- Run Pipeline.

## Documentation:
Some documentation is present in the code itself. It should be all straight-forward anyway.

## Contributions:
Contributions are more than welcome. Send a pull request and we'll go from there.

## Licences:
This project uses the Simplified BSD Licence. More information can be found inside [LICENCE](LICENCE)