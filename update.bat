echo "Your configurations backup to brighteyes_mcs\cfg.bck\"
xcopy /Y brighteyes_mcs\cfg\* brighteyes_mcs\cfg.bck\

echo "git fetch origin"
git fetch origin
echo "git reset --hard origin/master"
git reset --hard origin/master

echo Compiling the Cython code
python setup.py build_ext --inplace --force

xcopy /Y brighteyes_mcs\cfg.bck\* brighteyes_mcs\cfg\
