nanobot agent -m "Dime qué archivos hay en el directorio actual"
exit
nanobot agent -m "Dime qué archivos hay en el directorio actual"
exit
nanobot agent -m "Dime qué archivos hay en el directorio actual"
ls
ls ~
ls ~/.nanobot/
chown -R 1000:1000  ~
exit
python3 -m json.tool /home/nanobot/.nanobot/config.json > /dev/null && echo "✅ JSON válido"
cd /contenedores/conti-nanobot/nanobot
exit
