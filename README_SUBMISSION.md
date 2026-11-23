[Cliniko migration video](https://drive.google.com/file/d/19wFC0u23xh8BtP4e-JVYfEnV7TyKnRrP/view?usp=drive_link) | [Zanda migration video](https://drive.google.com/file/d/1xDO8zr5Piy-uky1h4cogzYDoWLjRiutN/view?usp=drive_link)

[My thought process during development](README_MIGRATION.md)

## Requirements

- Python 3.14 and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 24 or later and npm
- An OpenAI API key and access to the configured model

## Setup

From the repository root, install the Python dependencies and Chromium:

```powershell
python -m pip install uv
uv sync --locked
uv run --locked playwright install chromium
```

Copy replace `.env` with the provided `.env` and add your OpenAI API key.


Start the Carepatron mock in a separate terminal:

```powershell
cd carepatron
npm install
npm start
```

Open [http://localhost:4000](http://localhost:4000) and sign in with `you@practice.example` / `carepatron`.

## Run the migration

Run these commands from the repository root, with the mock running.

> NOTE: I started with cliniko which was a relly  bad choice. The login required an email code auth so If i get the email i will send the code to you ASAP. I am very sorry for this. This is the one that my app perfectly migrates for :(. lol


**Cliniko:**

```powershell
uv run --locked --env-file .env python main.py --source cliniko --stage all
```

Sign in manually in the browser, including the email verification code, then press Enter in the terminal to continue.



**Zanda:**

```powershell
uv run --locked --env-file .env python main.py --source zanda --stage all
```

The agent picks up the email and password from the .env file so does not need signing in. you just need to run it.


## How it works

The application runs separate practice, clients, appointments and notes stages. Each agent follows a Markdown playbook specific to the source and uses browser tools to collect data. The extracted records use Carepatron field names and retain source IDs for relationships. Python validates the saved JSON and imports it through the mock API, resolving source IDs to destination IDs.


## Videos

- [Cliniko migration video](https://drive.google.com/file/d/19wFC0u23xh8BtP4e-JVYfEnV7TyKnRrP/view?usp=drive_link)
- [Zanda migration video](https://drive.google.com/file/d/1xDO8zr5Piy-uky1h4cogzYDoWLjRiutN/view?usp=drive_link)

## My thoughts

### Architecture and choices

> I had very less time to think on the architetcure so i had made many architetual mistakes. 

I have recorded my though process and you can check it out here:

> My biggest mistake was not to use the provided API by the different platforms, which would have been much easier and acuurate as well. I should have included api adapters or MCP serever to allow the agent the API tools. 

> Another archtecture update would be to implement a JSON or data manager that allows tools to the agent to update/extract data as well as report back to the agent what is missing - what is wrong - what is ambigious so the agent can then fix and provdie those details. As well as it should do the validattion. Currently all of the data is centerent around the final AGENT response which is very prone to hillucination. 

> The migrator is very modular and new tools can be easily added and removed - like if you notice when i added the play book for the Zanda. I did not know that the time that their CSV export takes 2 hours so I asked the agent to extract the info one by one - and i added json record tool so they agent can keep on adding the extracted records that it can use later for the final stage result.

> I took some good decisions in model context management and also use the cheapest model - The whole development cost me 1.02$ and - 13M tokens were consumed.

> Extracting all of the data first into JSON reconds that are validated via mock Carepatron schema is i think a good seperation as it makes the app modular and can easily be updated to directly populate DB via API.

### What works well

> The agent perfetly follows instructions in the play book - every stage agent handles its instruction perfectly - agent can also get the records from the previous stage if it needs it - every thing is modular - new tools can be easily added - tried to kepth the agent loop minimal. 

### What could be better / more time

> I would have taken the time and navigated competetors websites and though on the architecture design more. which i did not do perfectly. 

> Using the provided API would have been my first choice - It would have made life easier as well as the records would be muct details and correct. 

> Again an intellegnt storage manager and more flexible tooling - I did not gave the agents much freedom to explore but that can be done - but that also consume tokens.

### Time spent and experience

> Around 2.5 days  - and I loved it - It was a great learning experience
