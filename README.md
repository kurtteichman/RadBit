Steps to setting up Radbit:

1. Creating an OpenAI key:
   - create an OpenAI account if you do not have one already
   - navigate to the API keys page
   - generate a new secret key (save this immediately)

2. Using Steamlit:
   - create a free Streamlit account
   - follow these steps: Create App -> Deploy a public app from GitHub
   - under 'Respository', enter 'eddie-benim/RadBit'
   - under 'Branch', enter 'main'
   - under 'Main File Path', enter 'radbit.py'
   - now press 'Deploy' to start the app
   - once the app has been created, return to 'My Apps' on your Streamlit home page. Find the app you just made and right-click on the three dots on the right side of      the app ribbon. Navigate to Settings -> Secrets and in the grey box, add the following: OPENAI_API_KEY="[your secret key]"
   
