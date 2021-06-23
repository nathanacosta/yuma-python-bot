'''
   - Python Selenium Bot
	Author: Nathan Acosta
	The University of Arizona
'''
#TODO - Add logging capabilities.
#TODO - Partial save when form cannot submit new entries.

#Standard Python Libraries
import os
import time
from os import system, name

#SQL and Pandas Libraries 
import pymysql # pip install pymysql
import pandas as pd # pip install pandas
from sqlalchemy import create_engine #pip install sqlalchemy


#Import Selenium Libraries // pip install selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0

#======[ SCRIPT VARIABLES ]=======#
os.chdir(os.path.dirname(os.path.abspath(__file__)))
working_directory = os.getcwd()

reboots = 0 		   # Reboots counter. Used for crash handling.

UPDATE_INTERVAL = 3600 # How many seconds the bot will wait before checking for new records.

#======[ END SCRIPT VARIABLES ]====#

# Clear Screen function
def clear():
  
    # for windows
    if name == 'nt':
        _ = system('cls')
  
    # for mac and linux(here, os.name is 'posix')
    else:
        _ = system('clear')


class SeleniumBot:

	def __init__(self):
		self.db_engine = None
		self.selenium_driver = None

	def botInit(self):
		print("Initializing Bot ...")
		time.sleep(1)
		try:
			self.connectDB()
			return "Success"
		except Exception as err:
			print(err)
			return "Error"

	def _confSelenium(self):
		print("Setting up Selenium Web Driver ...")
		try:
			options = Options()
			options.headless = False
			selenium_driver = webdriver.Firefox(options=options, executable_path='./driver/geckodriver')
			return selenium_driver
		except Exception as err:
			self.selenium_driver = None


	def checkUpdates(self):
		if(self.db_engine == None):
			raise Exception("Not connected to database!")
			return

		#Check if Index Cache Exists
		try:
			index_df = pd.read_pickle(working_directory + '/cache/index.pkl')
		except:
			print("No cache found! Fetching records...")
			with self.db_engine.connect() as connection:
				sql_df = pd.read_sql('SELECT * FROM wp_frmt_form_entry_view', con=connection) #Fetch form submissions
				index_df = sql_df.dropna(how="all").reset_index()
				index_df.to_pickle(working_directory + '/cache/index.pkl')
			
		with self.db_engine.connect() as connection:
			sql_df = pd.read_sql('SELECT * FROM wp_frmt_form_entry_view', con=connection)

		#Merge fetched records and check index cache
		merged_df = index_df.merge(sql_df, how="outer", indicator=True)
		new_records = merged_df.loc[merged_df['_merge'] == 'right_only'].iloc[:,:-1].to_dict('index')
		
		#Update index cache
		index_df.to_pickle(working_directory + '/cache/bkup_index.pkl')
		if len(new_records) != 0:
			merged_df.iloc[:,:-1].to_pickle(working_directory + '/cache/tmp_index.pkl') #Make temporary copy in case of crash

		return new_records

	def connectDB(self):
		print("Connecting to Database ...")
		try:
			db_connection_str = 'mysql+pymysql://python-bot:DataB0tEntry#501@localhost/wordpress'
			db_engine = create_engine(db_connection_str)

			self.db_engine = db_engine

		except Exception as err:
			print(err)
			self.db_engine = None
			return err

	def disconnectDB(self):
		try:
			self.db_engine.dispose()
		except Exception as err:
			print(err)

	def fillWebForm(self, new_entries_dict):
		#UA Fields HTML IDs
		webpage_dict = {
		'first_name': '//*[@id="form_913fa45e-b4ad-48d3-a26b-0e15918e3679"]',
		'last_name': '//*[@id="form_647beaf1-ccb7-4511-8a94-8bdadab42987"]',
		'email': '//*[@id="form_31880a0a-62ae-4e68-961b-a79cb7b53e76"]',
		'phone': '//*[@id="form_4d1766f7-7f38-4a86-8b7f-194ee76dd7ad"]',
		'school': '//*[@id="form_fc79dab1-9c5f-42ce-ba7e-9c07218a746f"]',
		'semester': '//*[@id="form_7ab361b8-930e-497c-b012-75b88f84447d"]',
		'program': '//*[@id="form_d88142c1-9660-4835-80f6-6c472d457eb9"]',
		'questions': '//*[@id="form_51e0d29e-1078-4f6d-a62a-376e615f7647"]'
        }
		submit = '//*[@id="form_7156f585-1060-4a2d-9bbb-3208433ebd56_container"]/div[3]/button'

		try:
			options = Options()
			options.headless = True
			bot_driver = webdriver.Firefox(options=options, executable_path='./driver/geckodriver')


			for entry in new_entries_dict:
				bot_driver.get("https://yuma.arizona.edu/")
				time.sleep(3)

				#Parse School Field 
				#(high-school and 'other' fields need to be handled separately due to Forminator creating a new column for these entries)
				for field in list(webpage_dict.keys()):
					if(new_entries_dict[entry][field] == "high-school" or 
					   new_entries_dict[entry][field] == 'other'):

						field_input = new_entries_dict[entry]['other']

					else:
						field_input = new_entries_dict[entry][field] 


					#handle drop-down fields
					if(field == "program"):
						#Switch input handling to Select method
						inputElement = Select(bot_driver.find_element_by_xpath(webpage_dict[field]))
						#Select based on text
						inputElement.select_by_visible_text(field_input)
					else:
						#Simple keyboard input
						bot_driver.find_element_by_xpath(webpage_dict[field]).send_keys(field_input)

					print(field_input)
				submit_button = bot_driver.find_element_by_xpath(submit)

				# Submit Entry
				submit_button.click()


				time.sleep(5)
			#Exit
			bot_driver.quit()
			#All entries have been uploaded to slate... save index cache and remove temporary file
			os.rename(working_directory + '/cache/tmp_index.pkl', working_directory + '/cache/index.pkl')
			print("New entries saved.")
		except Exception as err:
			print("Error while trying to input new entries into Slate form: ")
			print(err)
#--- end class SeleniumBot(...)

def loop(bot):
	try:
		while True:
			print("\nWaiting ...\n")

			time.sleep(UPDATE_INTERVAL)
			print("Checking for new entries ...")
			new_entries_dict = bot.checkUpdates()

			if len(new_entries_dict) == 0:
				print("No new entries found.")
			else:
				print("Found new entries!")
				print(new_entries_dict)
				bot.fillWebForm(new_entries_dict)
			
			#TODO - artificial bug.
			'''
			exception += 1
			if(exception > 1):
				print("woops, triped on a wire")
				raise Exception("Tripped on a wire!")
			'''
	except Exception:
		global reboots
		print(f"\nSomething crashed the bot. Attempting to restart ({reboots+1}) ...\n")
		time.sleep(3)
		crash_handler(bot)
# --- end loop(...)

def crash_handler(bot):
	global reboots
	#Delete instance of bot
	del bot
	if(reboots >= 3):
		print("\nMaximum reboots exceeded. Terminating ...\n")
		quit()

	reboots += 1
	main() #reboot
# --- end crash_handler(...)

def main():
	yumaBot = SeleniumBot()
	result = yumaBot.botInit()

	if result == "Success":
		print("\nSUCCESS!")
		loop(yumaBot)
	else:
		print("[ERROR] Failed to initate bot.")

if __name__ == '__main__':
	main()
