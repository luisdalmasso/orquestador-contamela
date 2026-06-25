# Estado del Sistema #

Analiza el conetnedor C:\Contenedores\conti-backend\docker-compose.conti.yml hay muchas rutas y datos desactualizados pero en lo central tiene 3 funciones un servidor mcp que expone muchas tools, un emulador de llm en el puerto 9001 qeu usa el agente hermes principal como agente llm (C:\Contenedores\conti-backend\app\hermes_profiles\contihome)  y luego agentes secundarios en C:\Contenedores\conti-backend\app\hermes_profiles\contihome\profiles estos agentes secundarios son chats de clientes con distintas funcionalidades ( mozo vistrual, asistente de odoo, etc)
Vas a ver muchas documentaciones antiguas contradictorias u otras muy especificas que no es importantes que las leas asi como configuraciones de rutas que quedaron obsoletas en distintas migraciones, por ello te doy esta explicacion para que encauses tu analisis del contenedor.

# Plan a desarrollar y problematica #
tengo dos problemas muy distintos a solucionar 
    - 1. El agente de codebiving y la forma de encarar el desarrollo y otras tareas internas de mi empresa de software
    - 2. Los Agentes secundarios o agentes llm de los clientes, son muy discolos, lleva mucho tiempo depurar las ahabilidades necesarias y mas ahun que cumplan las reglas estrictamente y tener trazabilidad
Estos dos de alguna manera se entremezckan y hoy estan totalmente acoplados, paso a detallarte mas para que puedas elaborar un plan para cadauno y uno global.
# 1 El agente de codebiving 
El agente de codebiving es un agente llm que se encarga de asistir a los desarrolladores en tareas de desarrollo, testing, debugging, etc. pero hermes no es su especialidad esta como el manejo de repositorios extensos. por otra parte cada cambio que se realiza o proyecto que se encara no queda documentado , no hay trazabilidad de las tareas realizadas, no se aprovecha el conocimiento de cada proyecto en curso o terminado, todo esto requeriria muchos cambios , muchas skills y reglas, etc.

** En la empresa tenemos dos areas desarrollo y marketing en esta ultima area realizamos campañas de marketing digital ( campañas seo, mailmarketing, redes sociales contenido multimedia) esto ultimo no estaba contemplado. Probe paperclip https://github.com/paperclipai/paperclip pero es mucho demasiado complejo demasiados agentes demasiada burocracia virtual para lo que necesito.**

Tal vez la solucion sea un conjunto de herramientas agentes, habilidades, workflows, etc, una enfocada en code y la otra en marketing preferiria una sola para ambos casos, por lo que estado investigando lo que creo en la vanguardia del mercado en este momento
He analizado los siguientes proyectos 
https://github.com/bytedance/UI-TARS 
https://github.com/coze-dev/coze-studio y https://github.com/coze-dev/coze-loop 
https://github.com/bytedance/deer-flow ( creo que este puede ser muy bueno para los agentes de los clientes, pero no se codificando y habria que ver la administracion de proyectos o tickets) 
https://github.com/HKUDS/DeepCode 
https://github.com/can1357/oh-my-pi ( este es importante tenerlo en cuanta por la economia de tokens, ver alternativas sino para mitigar esto en el codevibing) 
https://github.com/crewAIInc/crewAI 
https://github.com/EveryInc/compound-engineering-plugin
https://github.com/agent-infra/sandbox 
https://github.com/Hyperion-GPU/ProofFlow-v0.1 
https://github.com/volcengine/OpenViking
https://github.com/perplexityai/modelcontextprotocol
https://github.com/OpenHands/OpenHands 
https://github.com/DietrichGebert/ponytail
https://github.com/eyaltoledano/claude-task-master ( creo que se puede usar con otros cli, si fuera con claude el limitante es poder usar otros llms que los de antropic que es muy caro)
https://github.com/moorcheh-ai/memanto
https://github.com/harry0703/MoneyPrinterTurbo/
https://github.com/refactoringhq/tolaria
https://github.com/google/eng-practices
https://github.com/sourcebot-dev/sourcebot
https://github.com/kyegomez/swarms


# 2 los agentes clientes # 
Alo mencionado sobre stos agentes, vuelvo a desatacra que debe ser sencillo incorporarle skills y flujos de trabajos mediante reglas y estados y que no se salgan de esto, tambien es importante que manejen ademas de http los clientes telegram y whatsapp este ultimo por bayleys o similar como hace hermes, ya que tener todo centralizado en un servidor como wppconnect es muy inestable 

# Trabajo solicitado #
Debes realizar un analisis de las alternativas detallado y un  plan en el archivo 'Plan_backend.md' El plan debe
incluir un detalle del analisis de cada herramienta que te he mencionado debes realizar analisis de herramientas excluyentes, las que se potencian y encontrar el mejor conjunto y optimizacion.
Si conoces herreamientas necesarias y que no estan aqui o son mejores y mas adecuadas tammbien las puedes incluir en el plan de remplazo del los agentes de codevibing / Marketing y los agentes clientes
