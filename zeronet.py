from src import main

action_func = getattr(main, main.config.action)
action_kwargs = main.config.getActionArguments()

action_func(**action_kwargs)

