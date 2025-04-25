import configparser

app_config = configparser.ConfigParser()
app_config.read('config/config.ini')

def override_config(new_config:dict):
    for option, value in new_config.items():
        app_config.set("trading", option, str(value))

    with open("config/config.ini", "w") as configfile:
        app_config.write(configfile)