# Run the python and node installs
pip3 install -r requirements.txt

cd nodejs
npm install package.json
cd ..

echo "Finished installing packages"