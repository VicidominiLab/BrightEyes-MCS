import os
import subprocess
import sys


def check_vs_build_tools():
    try:
        # Check if vswhere.exe is available
        vswhere_path = os.path.join(os.environ['ProgramFiles(x86)'], 'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
        if not os.path.exists(vswhere_path):
            print("vswhere.exe not found. Please ensure Visual Studio Installer is installed.")
            return False

        # Run vswhere to find installed instances with C++ build tools
        result = subprocess.run([vswhere_path, '-products', '*', '-requires', 'Microsoft.VisualCpp.Tools.HostX86.TargetX86', '-find', 'VC\\Tools\\MSVC\\*\\bin\\Hostx64\\x64\\cl.exe'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.stdout:
            print("Visual Studio C++ Build Tools are installed.")
            print("VS C++ Compiler Path:", result.stdout.strip())
            return True
        else:
            print("Visual Studio C++ Build Tools are not installed.")
            return False
    except Exception as e:
        print(f"Error checking for VS Build Tools: {e}")
        return False

def check_msys2():
    try:
        # Check if MSYS2 is installed by checking the default installation path
        msys2_default_path = r"C:\msys64\usr\bin\bash.exe"
        if os.path.exists(msys2_default_path):
            print("MSYS2 is installed.")
            print("MSYS2 Path:", msys2_default_path)
            msys2_path = msys2_default_path
            msys2_path = r"C:\msys64"
            return True, msys2_path
        else:
            print(f"Not found MSYS2.")
            return False, ""
    except Exception as e:
        print(f"Error checking for MSYS2: {e}")
        return False, ""

def build_cython_with_vs(): 
    """Builds the Cython part of the code using Visual Studio (MSVC)."""
    try:
        print("Building the Cython part of the code with Visual Studio (MSVC)...")
        subprocess.run(['python', 'setup.py', 'build_ext', '--inplace', '--force', "--verbose"], check=True, shell=True, env=os.environ)
        print("Cython build with Visual Studio completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during Cython build with Visual Studio: {e}")
        sys.exit(1)
        
def build_cython_with_msys2(msys2_path):
    """Builds the Cython part of the code using MSYS2 (mingw32)."""
    try:
        bash_path = msys2_path + os.path.sep + "usr" + os.path.sep + "bin"  + os.path.sep + "bash.exe"
        bash_cmd =  'pacman --noconfirm -Sy mingw-w64-ucrt-x86_64-gcc'
        print("Installing GCC with MSYS2.")        
        subprocess.run([bash_path, '-lc', bash_cmd], check=True, shell=True, env=os.environ)
        print("GCC installation done.")        
    except subprocess.CalledProcessError as e:
        print(f"Error during installing GCC with MSYS2: {e}")
        
    try:
        env = os.environ
        path = env["PATH"]        
        path1 = msys2_path + os.path.sep + "usr" + os.path.sep + "bin"
        path2 = msys2_path + os.path.sep + "ucrt64" + os.path.sep + "bin"        
        path = path + r";" + path1 + r";" + path2 + r";"
        os.environ["PATH"]=path
        
        
        print("Building the Cython part of the code with MSYS2 (mingw32)...")
        
        
        subprocess.run(['python', 'setup.py', 'build_ext', '--inplace', '--force', '--compiler=mingw32', '-DMS_WIN64'], check=True, shell=True, env=os.environ)
        print("Cython build with MSYS2 completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during Cython build with MSYS2: {e}")
        sys.exit(1)
        
        
if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv or "/?" in sys.argv:
        print("This script help to compile BrightEyes-MCS libaries written in Cython\r\n\r\n"
              "Arguments\r\n"
              "[no arguments] = Try to compile with Visual Studio C++ if not found use MSYS2\r\n"
              "--force_msys2  = Force compilation with MSYS2\r\n"
              "--force-vs     = Force compilation with Visual Studio C++\r\n")
        exit()
    
    vs_installed = check_vs_build_tools()
    msys2_installed, msys2_path = check_msys2()
       
    force_msys2 = '--force-msys2' in sys.argv
    force_vs = '--force-vs' in sys.argv

    if force_msys2:
        print("Force compilation with MSYS2")
    if force_vs:
        print("Force compilation with MSVSC")

    if (vs_installed or force_vs) and not force_msys2:
        build_cython_with_vs()

    elif (msys2_installed or force_msys2) and not force_vs:
        build_cython_with_msys2(msys2_path)
    else:
        print("NO COMPILER FOUND!!")
        
    from test import check_cython_lib
    check_cython_lib.test()
    