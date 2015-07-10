#!/bin/bash
####
## PARAMETERS
####
# $1: Python Script Location (in S3)
# $2: S3 Bucket where emails are stored
# $3: S3 Prefix to emails (inside the bucket stated in $2)
# $4: AWS S3 Bucket Region
# $5: Processed Emails JSON Link (inside S3 bucket stated in $2)
# $6: Access Key (for S3)
# $7: Secret Key (for S3)
# $8: Administrator Email (for stats) -- optional

####
## STARTING
####
echo "START : " `date`

####
## DOWNLOADING PYTHON SCRIPT FROM S3
####
echo "DOWNLOADING PYTHON SCRIPT FROM S3 : " `date`
aws s3 cp s3://$1 /home/ec2-user/

####
## RUNNING PYTHON SCRIPT
####
echo "RUNNING PYTHON SCRIPT : " `date`
# this removes the path from the location, leaving just the filename.
echo "PARAMETERS PASSED: `echo $1 | sed 's,^[^ ]*/,,'` -b $2 -p $3 -r $4 -e $5 -k $6 -s $7 -a $8"
python /home/ec2-user/`echo $1 | sed 's,^[^ ]*/,,'` -b $2 -p $3 -r $4 -e $5 -k $6 -s $7 -a $8

####
## FINISHING
####
echo "FINISHED : " `date`
