Initial Architecture Thoughts:

> I want the migrator to be completely modular so it can easily be connected with different LLM Models. The Tooling are also modular and tools can be added or removed as needed.

> This is a squential complex task so I don't want a single agent to do every thing as it will drastically increase the context size and I will have to pay MORE 😀. Even for the business we can have squential agents where we have a login agent and that can just login to any competetor portal and then it should give a small report back and that report can then be appended - so the context is not bloated with unecessary messages.

> I now have a working agent which can use the tools. I can include unit tests to these the moduels that i have written for now. but due to lack of time i will procedd with picking up a competetor and just first setting up the login agent first and try to keep it modular and cofigurable via source specific configs.