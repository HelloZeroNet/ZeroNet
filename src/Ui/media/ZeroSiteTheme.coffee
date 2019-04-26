DARK = "(prefers-color-scheme: dark)"
LIGHT = "(prefers-color-scheme: light)"

mqDark = window.matchMedia(DARK)
mqLight = window.matchMedia(LIGHT)


changeColorScheme = (theme) ->
    zeroframe.cmd "userGetGlobalSettings", [], (user_settings) ->
        if user_settings.theme != theme
            user_settings.theme = theme
            zeroframe.cmd "userSetGlobalSettings", [user_settings]

            location.reload()

        return
    return


displayNotification = ({matches, media}) ->
    if !matches
        return

    zeroframe.cmd "wrapperNotification", ["info", "Your system's theme has been changed.<br>Please reload site to use it."]
    return


detectColorScheme = ->
    if mqDark.matches
        changeColorScheme("dark")
    else if mqLight.matches
        changeColorScheme("light")

    mqDark.addListener(displayNotification)
    mqLight.addListener(displayNotification)

    return


zeroframe.cmd "userGetGlobalSettings", [], (user_settings) ->
    if user_settings.use_system_theme == true
        detectColorScheme()

    return
