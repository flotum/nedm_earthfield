import httplib2
import os
import base64
from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools
import datetime as dt
import numpy as np
from pprint import pprint as pp

class gmailImport():
	
	SCOPES = 'https://www.googleapis.com/auth/gmail.readonly'
	CLIENT_SECRET_FILE = 'client_id.json'
	APPLICATION_NAME = 'nEDMEarthField'
	
	def getCredentials(self):
	    """Gets valid user credentials from storage.
	    If nothing has been stored, or if the stored credentials are invalid,
	    the OAuth2 flow is completed to obtain the new credentials.
	    Returns:
	        Credentials, the obtained credential.
	    """
	    home_dir = os.path.expanduser('~')
	    credential_dir = os.path.join(home_dir, '.credentials')
	    if not os.path.exists(credential_dir):
	        os.makedirs(credential_dir)
	    credential_path = os.path.join(credential_dir, 'nedm_earthfield_gmail.json')
	
	    store = oauth2client.file.Storage(credential_path)
	    credentials = store.get()
	    if not credentials or credentials.invalid:
	        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
	        flow.user_agent = APPLICATION_NAME
	        if flags:
	            credentials = tools.run_flow(flow, store, flags)
	        else: # Needed only for compatibility with Python 2.6
	            credentials = tools.run(flow, store)
	        print('Storing credentials to ' + credential_path)
	    return credentials
			
	
	def getEarthField(self, from_dt, to_dt=0):
		#from_dt and to_dt are datetime objects indicating the time interval of requesting earth field data
		credentials = self.getCredentials()
		http = credentials.authorize(httplib2.Http())
		service = discovery.build('gmail', 'v1', http=http)
		#only return data from one email if no end date is given OR end is before start
		if to_dt == 0 or from_dt >= to_dt: 
			to_dt = from_dt + dt.timedelta(days=1)
		else: to_dt = to_dt + dt.timedelta(days=1)
		query = "from:obs@geophysik.uni-muenchen.de after:" + from_dt.strftime("%Y/%m/%d") + " before:" + to_dt.strftime("%Y/%m/%d")
		print(query)
		mail = service.users().messages().list(userId='me',q=query).execute()
		
		bodies = {}
		timestamp = []
		bx = np.array([], dtype=float)
		by = np.array([], dtype=float)
		bz = np.array([], dtype=float)
		btot = np.array([], dtype=float)
		
		if 'messages' in mail:
			num_mails = len(mail['messages'])
			dt_str = "%Y-%m-%d %H:%M"
			count = 1
			for k in reversed(mail['messages']):
				body = service.users().messages().get(userId='me', id=k['id'], format='full').execute()
				body = str(base64.urlsafe_b64decode(body['payload']['body']['data'].encode('ascii')))
				start_dt = from_dt
				end_dt = to_dt
				if start_dt.minute != 0:
					start_dt = self.roundtoMinute(from_dt, way="up")
				if end_dt.minute != 0:
					end_dt = self.roundtoMinute(to_dt, way="down")
				#add one day for each iteration, first iteration add 0 days
				start_dt = start_dt + dt.timedelta(days = count - 1)
				end_dt = end_dt + dt.timedelta(days = -num_mails + count - 1)
				if num_mails == 1:					
					#one email requested
					start_str = start_dt.strftime(dt_str)
					#to make the string find work we have to find the line of one minute after the requested time
					end_str = (end_dt + dt.timedelta(minutes=1)).strftime(dt_str)
				else:
					#more than one mail requested
					if count == 1:
						#in first run with more files change end to last measurement at 23:59
						start_str = start_dt.strftime(dt_str)
						end_str = (end_dt.replace(hour=0, minute=0) + dt.timedelta(days=1)).strftime(dt_str)
					elif count == num_mails:
						#last email in query, then use start at 00:00 and end as requested
						start_str = start_dt.replace(hour=0, minute=0).strftime(dt_str)
						#to make the string find work weave to find the line of one minute after the requested time
						end_str = (end_dt + dt.timedelta(minutes=1)).strftime(dt_str)
					else:
						#all other mails that are not the first or last one
						start_str = start_dt.replace(hour=0, minute=0).strftime(dt_str)
						end_str = (end_dt.replace(hour=0, minute=0) + dt.timedelta(days=1)).strftime(dt_str)
				print("start: {} - end {}".format(start_str,end_str))
				#finds the data in the email in the specified time range
				data = body[body.find(start_str):body.find(end_str)].split()
				#parse the date and time information in the email data into a datetime obj to be returned
				timestamp = timestamp + [dt.datetime.strptime(data[::7][i] + data[1::7][i], "%Y-%m-%d%H:%M:%S.%f") for i in range(len(data[::7]))]
				bx = np.append(bx, np.array(data[3::7], dtype=float))
				by = np.append(by, np.array(data[4::7], dtype=float))
				bz = np.append(bz, np.array(data[5::7], dtype=float))
				btot = np.append(btot, np.array(data[6::7], dtype=float))
				count = count + 1
			print("Recieved {} emails.".format(num_mails))
			return {'datetime': timestamp, 'bx':bx, 'by':by, 'bz':bz, 'btot':btot }
		else:
			print("No new emails.")
			return {}
		
	def roundtoMinute(self, timestamp, way="up"):
		#seconds of the day
		seconds = (timestamp - dt.datetime.min).seconds
		#round to 60 seconds
		round_to = 60
		if way == "down":
			rounding = (seconds + round_to/2) // round_to * round_to
		else: #rounds up
			rounding = (seconds + round_to) // round_to * round_to
		
		return timestamp + dt.timedelta(seconds=rounding-seconds)

def main():
    gmail = gmailImport()
    #start and end are datetime obj (year, month, day, [hour, minute])
    start = dt.datetime(2015, 11, 7)
    end = dt.datetime(2015, 11, 7, 23, 59)
    #returns dictonary of keys 'datetime', 'bx', 'by', 'bz', 'btot'
    field = gmail.getEarthField(start, end)
    #convert datetime list to difference in seconds to the first timestamp
    time_s = np.array([(m-start).total_seconds() for m in field['datetime']], dtype=float)
    pp(time_s)
    pp(field['btot'])

if __name__ == '__main__':
    main()
