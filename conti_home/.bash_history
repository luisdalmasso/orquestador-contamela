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
set +H; export PROMPT_COMMAND='export PS1="
###PS1JSON###
{
  \"pid\": \"$!\",
  \"exit_code\": \"$?\",
  \"username\": \"\\u\",
  \"hostname\": \"\\h\",
  \"working_dir\": \"$(pwd)\",
  \"py_interpreter_path\": \"$(command -v python || echo \\"\\")\"
}
###PS1END###
"'; export PS2=""
clear
git rev-parse --abbrev-ref HEAD
clear
git config --global --add safe.directory /compose && git -C /compose rev-parse --abbrev-ref HEAD
clear
set +H; export PROMPT_COMMAND='export PS1="
###PS1JSON###
{
  \"pid\": \"$!\",
  \"exit_code\": \"$?\",
  \"username\": \"\\u\",
  \"hostname\": \"\\h\",
  \"working_dir\": \"$(pwd)\",
  \"py_interpreter_path\": \"$(command -v python || echo \\"\\")\"
}
###PS1END###
"'; export PS2=""
clear
git rev-parse --abbrev-ref HEAD
clear
