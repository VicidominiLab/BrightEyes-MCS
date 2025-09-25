from win32com.client import Dispatch
import winreg
import os, sys

user_profile = os.environ['USERPROFILE']
desktop_registry_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"

try:
    # Open the Registry key
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, desktop_registry_key) as key:
        # Query the Registry key to get the desktop folder path
        desktop_path, _ = winreg.QueryValueEx(key, "Desktop")
    desktop_path = desktop_path.replace("%USERPROFILE%", user_profile)
    print("Desktop Path:", desktop_path)

except Exception as e:
    print("Error:", e)

path = os.getcwd()+r"\BrightEyesMCS.lnk"  #This is where the shortcut will be created
target = os.getcwd()+r"\run.bat" # directory to which the shortcut is created
icon =  os.getcwd()+r"\brighteyes_mcs\images\icon.ico"
print("Creating link: ", path)
shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(path)
shortcut.IconLocation = icon
shortcut.Targetpath = target
shortcut.save()


path = desktop_path+r"\BrightEyesMCS.lnk"  #This is where the shortcut will be created
print("Creating link: ", path)
shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(path)
shortcut.IconLocation = icon
shortcut.Targetpath = target
shortcut.save()


working_path = os.getcwd()


path = os.getcwd()+r"\Python (.venv BrightEyesMCS).lnk"  #This is where the shortcut will be created
target = os.getcwd()+r"\enter_in_venv.bat" # directory to which the shortcut is created
icon =  sys.executable+",0"
print("Creating link: ", path)
shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(path)
shortcut.IconLocation = icon
shortcut.Targetpath = target
shortcut.WorkingDirectory = working_path
shortcut.save()


path = desktop_path+r"\Python (.venv BrightEyesMCS).lnk"  #This is where the shortcut will be created
print("Creating link: ", path)
shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(path)
shortcut.IconLocation = icon
shortcut.Targetpath = target
shortcut.WorkingDirectory = working_path
shortcut.save()
