# Guia passo a passo para executar o CTRL-Lab

Este guia descreve como preparar o Raspberry Pi OS Lite 64-bit, conferir a montagem, iniciar o runtime no Raspberry Pi e abrir o dashboard no computador por SSH. A sequência recomendada começa sem modelos de IA: primeiro valide comunicação e sensores; depois, adicione a pré-visualização da câmera.

> **Limites do protótipo:** o modo de pré-visualização descrito aqui transmite vídeo, mas não detecta fogo, fumaça ou EPI. A inferência visual exige modelos ONNX treinados e compatíveis, que não estão incluídos no repositório. O sistema é experimental e não substitui alarmes nem dispositivos certificados de segurança.

## Início automatizado no Windows

Para executar automaticamente os passos de sincronização do código, instalação das dependências, inicialização dos sensores/câmera, criação dos túneis SSH e abertura do dashboard, execute na raiz do repositório:

```powershell
.\start-ctrlab.ps1
```

Se o PowerShell bloquear a execução do arquivo, inicie-o sem alterar a política permanente do computador:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-ctrlab.ps1
```

O script usa por padrão o usuário SSH `ctrl-lab` e o IP atual `192.168.15.75`. Após conectar, consulta `hostname -I` para mostrar os endereços atuais do Pi. Se o IP mudar, informe outro host pelo parâmetro `-RaspberryHost`, por exemplo `.\start-ctrlab.ps1 -RaspberryHost 192.168.15.80`. Na primeira execução, se ainda não houver a chave de automação no Pi, o script cria uma chave Ed25519 local protegida pela conta do Windows e solicita a senha SSH uma vez para instalar a chave pública; depois, SSH, SCP e o túnel reutilizam essa chave. O script nunca lê nem grava a senha. Se o Pi solicitar senha `sudo` para instalar pacotes de sistema, essa autenticação é separada. Ele cria um ambiente virtual local em `.venv`, instala as dependências no PC e no Raspberry Pi, copia os módulos Python necessários e abre janelas separadas para o dashboard e o túnel. Se houver um runtime CTRL-Lab anterior iniciado no mesmo diretório, ele o encerra graciosamente antes de iniciar outro; outros processos e runtimes de caminhos diferentes não são encerrados. Quando a página abrir, use no campo de controle o token que o script mostra no terminal.

Por padrão inicia a **pré-visualização sem IA** (não detecta incêndio, fumaça ou EPI). Requer SSH e SCP do OpenSSH disponíveis no Windows, Python no PC, Mosquitto configurável por `sudo` no Pi, câmera conectada e portas locais 8000, 1884 e 8081 livres. O script não copia modelos ONNX, não salva tokens em arquivo e interrompe a inicialização se já encontrar outro runtime ativo. O runtime iniciado no Pi permanece rodando após fechar o script; pare-o com o comando que o script informa ou com `Ctrl+C` na sessão do Pi. Confira os logs se câmera ou sensores não estiverem disponíveis.

## 1. O que será necessário

- Raspberry Pi com Raspberry Pi OS Lite 64-bit, acessível por SSH.
- PC com o repositório CTRL-Lab e Python instalado.
- Raspberry Pi e PC alcançáveis pela mesma rede ou por SSH.
- Broker MQTT Mosquitto no Raspberry Pi.
- Para o teste completo: PS3 Eye USB, DHT22 e, se disponíveis, MQ-2, buzzer e botões.
- Fonte adequada para o Raspberry Pi e componentes; não alimente cargas de maior corrente diretamente pelos GPIOs.

No PC, abra o terminal PowerShell na pasta do repositório:

```powershell
Set-Location C:\Projects\CTRL-Lab
```

No restante do guia, substitua `ctrl-lab` pelo usuário SSH real do Raspberry Pi e `192.168.1.50` pelo endereço IP real do dispositivo. Para localizar o endereço no Pi:

```bash
hostname -I
```

## 2. Conferir a montagem elétrica

Desligue o Raspberry Pi antes de montar ou alterar os fios. Os números abaixo são pinos **BCM**, não números físicos do conector.

| Componente | Conexão ao Raspberry Pi |
|---|---|
| DHT22 | DATA → GPIO17; VCC → 3,3 V; GND → GND |
| Buzzer | Sinal de controle → GPIO23; use driver apropriado se necessário |
| Saída digital DO do MQ-2 | DO → GPIO5, somente após confirmar que o nível não ultrapassa 3,3 V |
| Botão de emergência normalmente aberto | Entre GPIO6 e GND |
| Botão de reset normalmente aberto | Entre GPIO13 e GND |
| PS3 Eye | USB |

Para um DHT22 sem módulo, use resistor pull-up de aproximadamente 4,7 kΩ entre DATA e 3,3 V. Confirme se um módulo pronto já possui esse resistor.

O MQ-2 é lido somente pela saída digital DO: o projeto não mede ppm nem usa a saída analógica. Alguns módulos alimentados em 5 V podem produzir 5 V na saída; use divisor ou conversor de nível apropriado e confirme com multímetro antes de conectar ao GPIO. O padrão do software considera detecção ativa em LOW; use `--mq2-active-high` se o módulo indicar detecção em HIGH.

Os botões usam pull-up interno e devem fechar para GND, nunca para 3,3 V ou 5 V. O botão de emergência com trava precisa ser destravado mecanicamente; depois, pressione o botão separado de reset. A parada implementada pelo software não desliga a alimentação do Pi e não é uma parada de emergência elétrica certificada.

Mais detalhes de montagem e segurança estão em [MATERIAIS_E_MONTAGEM.md](./MATERIAIS_E_MONTAGEM.md).

## 3. Preparar o Raspberry Pi

Conecte-se pelo PowerShell:

```powershell
ssh ctrl-lab@192.168.1.50
```

No terminal SSH, confirme arquitetura e sistema:

```bash
uname -m
python3 --version
cat /etc/os-release
```

Em uma instalação de 64 bits, `uname -m` normalmente retorna `aarch64`. Entre na pasta do projeto. Se o repositório ainda não estiver no Pi, clone-o; caso já esteja, sincronize-o sem descartar alterações locais:

```bash
cd ~/CTRL-Lab
git status --short
git pull
```

Se `git status --short` mostrar alterações locais relevantes ou o `git pull` não puder prosseguir, pare e resolva a sincronização antes de iniciar. Mantenha os arquivos do runtime na mesma versão — especialmente `main.py`, `sensors.py`, `camera_preview.py` e `alerts.py` — para evitar erros por cópia parcial ou incompatibilidade.

Instale ferramentas de sistema e o Mosquitto:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-rpi-lgpio libgpiod-dev mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

Crie o ambiente virtual com acesso às bibliotecas do sistema, ative-o e instale as dependências Python:

```bash
cd ~/CTRL-Lab
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install adafruit-circuitpython-dht
python -m pip install 'gpiod>=2.2.2,<3'
```

O driver do DHT22 requer a biblioteca de sistema `libgpiod` e os módulos Python `gpiod` e `RPi.GPIO`. O script instala `gpiod` no ambiente virtual e adiciona ao venv o caminho `/usr/lib/python3/dist-packages`, de onde o sistema instala `RPi.GPIO`. No Raspberry Pi OS Bookworm/Trixie, esse módulo vem do pacote compatível `python3-rpi-lgpio`; em versões anteriores, use `python3-rpi.gpio`. Evite instalar os dois juntos: em Trixie, `python3-rpi.gpio` pode remover `python3-rpi-lgpio`. Não instale `rpi-lgpio` pelo pip nesse fluxo, pois isso exige compilar `lgpio` e ferramentas como SWIG sem necessidade. Se aparecer um aviso de que GPIO real não está disponível, não considere o buzzer, os botões ou o MQ-2 validados fisicamente.

Nos próximos acessos por SSH, reative o ambiente:

```bash
cd ~/CTRL-Lab
source .venv/bin/activate
```

## 4. Validar o programa sem hardware

Com o ambiente virtual ativado, rode um teste curto simulado:

```bash
python -m raspberry_pi.main --mock --cycles 2
```

Isso valida o fluxo básico com leituras simuladas e encerra após duas atualizações de status. Não valida GPIO, DHT22, câmera ou conexão MQTT.

## 5. Validar o Mosquitto no Raspberry Pi

Em uma janela SSH no Raspberry Pi, confirme que o serviço está ativo:

```bash
sudo systemctl status mosquitto --no-pager
```

Em outra sessão SSH para o Pi, assine o tópico de status:

```bash
mosquitto_sub -h localhost -t ctrlab/raspberry/status -v
```

Quando o runtime estiver ligado, deverão aparecer mensagens JSON aproximadamente uma vez por segundo e também quando o estado mudar. Use `Ctrl+C` para sair do assinante.

## 6. Testar sensores e botões sem câmera

Com os componentes conectados e a montagem revisada, inicie o runtime real no Pi:

```bash
cd ~/CTRL-Lab
source .venv/bin/activate
python -m raspberry_pi.main --broker localhost
```

O programa continua rodando até ser interrompido com `Ctrl+C`. Observe os logs:

- `Conectado ao broker MQTT com código 0`: conexão local ao Mosquitto estabelecida.
- `Leitura -> ... => NORMAL`: estado atual; `NORMAL` não confirma que sensores sem leitura estejam seguros.
- `temp=NoneC` e `umid=None%`: DHT22 indisponível, ainda não validado ou leitura vencida.
- `dht_age=...s`: idade da última leitura válida do DHT22.
- `gas_detected`: estado digital do MQ-2, não uma medida de concentração.

O DHT22 é consultado a cada 5 segundos por padrão (o mínimo efetivo continua sendo 2 segundos). Essa redução diminui as leituras do DHT22, mas não reduz diretamente o trabalho da câmera. Uma última leitura boa é mantida por até 12 segundos para permitir uma nova tentativa após uma falha; depois, temperatura e umidade voltam a `None`. O campo `dht_age_seconds` informa a idade do valor. MQ-2 e botões continuam sendo verificados no loop de controle a 48 Hz.

Teste o botão de emergência: deve entrar em `EMERGENCY` e permanecer travado mesmo depois de soltar o botão. Destrave-o mecanicamente e pressione reset. Sem modelo de segurança, o reset só pode confirmar sensores e botões, não uma condição visual segura.

Se temperatura/umidade falharem repetidamente, teste primeiro o DHT22 com a câmera desconectada. Confira alimentação de 3,3 V, GND comum, DATA no GPIO17 e pull-up; então teste o passo seguinte. A execução sequencial reduz a concorrência intencional de captura e leitura no modo sem IA, mas não corrige problemas de cabeamento, alimentação, USB, driver ou escalonamento do Linux.

## 7. Testar a PS3 Eye localmente

Interrompa o runtime anterior com `Ctrl+C`. Com a câmera conectada, rode um teste isolado:

```bash
python -m raspberry_pi.main --camera-test --camera-device 0 --camera-test-frames 30
```

O teste informa número de frames, FPS e resolução e termina sem iniciar GPIO/MQTT. Se a câmera não for encontrada, confirme o dispositivo e tente outro índice com `--camera-device`.

## 8. Iniciar a pré-visualização sem IA

Use um token de câmera aleatório com pelo menos 16 caracteres e mantenha-o privado. Escolha um token separado do token de controle do dashboard. Na sessão SSH do Raspberry:

```bash
export CTRL_LAB_CAMERA_TOKEN="substitua-por-um-segredo-aleatorio-com-mais-de-16-caracteres"
python -m raspberry_pi.main \
  --broker localhost \
  --camera-device 0 \
  --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN" \
  --camera-stream-host 127.0.0.1
```

Esse modo **não** fornece `--safety-model`: transmite apenas a pré-visualização, sem análise de fogo, fumaça ou EPI. A imagem é configurada para 640×480 (VGA, 4:3) e a captura/codificação é síncrona, com alvo de até 24 FPS. O driver pode não aceitar exatamente a resolução ou a taxa solicitadas, e a captura/codificação pode reduzir a cadência efetiva e atrasar o loop. O loop de controle roda a 48 Hz; o DHT22 é consultado a cada 5 segundos por padrão, e a última leitura boa é mantida por até 12 segundos. MQ-2 e botões continuam sendo verificados a 48 Hz. Logs e status são enviados a cada segundo. 24 FPS aumenta o uso de CPU e USB e pode afetar o timing ou a estabilidade do DHT22; valide os logs de idade/falhas do sensor no Raspberry. A execução não é de tempo real e não garante ausência total de contenção ou de falhas de sensor.

O servidor da câmera fica vinculado a `127.0.0.1` no Pi, acessível somente localmente. Não altere para `0.0.0.0` ao usar túnel SSH sem necessidade.

## 9. Conectar o PC ao Raspberry por túnel SSH

Para manter o broker MQTT local no Raspberry e não expô-lo à rede, abra **uma segunda janela do PowerShell no PC** e mantenha o túnel ativo:

```powershell
ssh -N -L 1884:127.0.0.1:1883 -L 8081:127.0.0.1:8081 ctrl-lab@192.168.1.50
```

Esse túnel encaminha a porta local `1884` do PC para o Mosquitto `1883` do Pi, e a porta local `8081` para o stream da câmera. Mantenha a janela aberta enquanto usar o dashboard. Se o comando falhar porque a porta local já está ocupada, escolha outra porta local e ajuste `--mqtt-port` ou a URL da câmera conforme necessário.

## 10. Iniciar o dashboard no Windows

Abra outra janela do PowerShell no PC, na pasta do projeto. Instale as dependências, se ainda não estiverem instaladas:

```powershell
Set-Location C:\Projects\CTRL-Lab
python -m pip install -r requirements.txt
```

Defina dois tokens aleatórios distintos, cada um com pelo menos 16 caracteres. O token de câmera precisa ser igual ao definido em `CTRL_LAB_CAMERA_TOKEN` no Raspberry:

```powershell
$env:CTRL_LAB_DASHBOARD_TOKEN = "token-de-controle-aleatorio-com-mais-de-16-caracteres"
$env:CTRL_LAB_CAMERA_TOKEN = "mesmo-token-de-camera-configurado-no-raspberry"
```

Inicie o dashboard conectado às portas locais do túnel:

```powershell
python -m central.dashboard `
  --host 127.0.0.1 `
  --port 8000 `
  --broker 127.0.0.1 `
  --mqtt-port 1884 `
  --control-token "$env:CTRL_LAB_DASHBOARD_TOKEN" `
  --camera-stream-token "$env:CTRL_LAB_CAMERA_TOKEN" `
  --camera-stream-url http://127.0.0.1:8081/video.mjpg
```

Abra `http://127.0.0.1:8000` no navegador do PC e informe o token de controle na interface para habilitar o comando remoto. O dashboard deverá mostrar o estado MQTT, as leituras e o vídeo. O controle de acesso por dashboard só funciona se um serviço de visão estiver executando com `--safety-model` e, para habilitar a verificação de EPI, com `--access-model` compatível.

> Em versões antigas do PowerShell, ou se preferir evitar problemas de continuação de linha, execute o mesmo comando numa única linha. Passe os tokens como argumentos entre aspas usando `$env:NOME_DA_VARIAVEL`; variáveis não definidas, como `$Token`, fazem o programa reclamar que o argumento está faltando.

O dashboard e o túnel acima ficam restritos ao PC local. Para abrir a interface a outros dispositivos da rede, isso exige uma decisão de rede/firewall consciente; não exponha o dashboard HTTP nem o broker MQTT à Internet.

## 11. Execução com modelos ONNX (etapa posterior)

Os pesos ONNX não acompanham o repositório. Só avance quando tiver modelos treinados/exportados e compatíveis com o runtime e com as classes configuradas. No Raspberry, coloque os arquivos em um diretório de modelos e inicie com os caminhos reais:

```bash
python -m raspberry_pi.main \
  --broker localhost \
  --camera-device 0 \
  --safety-model models/ctrlab-safety.onnx \
  --access-model models/ctrlab-access.onnx \
  --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN"
```

Esse exemplo só funcionará quando ambos os arquivos existirem e forem compatíveis. O modelo de segurança deve usar as classes `smoke,fire`; o modelo de acesso deve corresponder a `person,lab_coat,trousers,closed_shoes,long_hair,tied_hair`, na ordem de saída do modelo. O acesso inicia desabilitado e pode ser alternado pelo atalho `A` no terminal ou pelo dashboard. Desabilitar o acesso não desativa a segurança contínua.

O modo ONNX usa `RaspberryVisionService`, com captura/inferência próprias em threads; portanto, não é o mesmo escalonamento cooperativo da pré-visualização sem IA. Meça comportamento e carga no Pi antes de deixar essa configuração em operação.

## 12. Encerrar a execução

1. Interrompa o runtime no Pi com `Ctrl+C`.
2. Interrompa o dashboard no PC com `Ctrl+C`.
3. Interrompa o túnel SSH com `Ctrl+C`.
4. Se estiver trabalhando com a montagem, desligue o Pi antes de mexer nos fios.

## 13. Diagnóstico rápido

| Sintoma | O que conferir |
|---|---|
| Dashboard sem status e `MQTT desconectado` | Runtime em execução, Mosquitto ativo, túnel SSH aberto e porta local `1884` correta |
| Stream da câmera retorna `403 Forbidden` | Mesmo token de câmera no Pi e no dashboard; token com pelo menos 16 caracteres |
| Stream retorna `503` ou não conecta | Runtime com `--camera-stream-token`, servidor de câmera ativo e túnel da porta `8081` aberto |
| `temp=NoneC` / `umid=None%` | Dependência `adafruit-circuitpython-dht`, biblioteca `libgpiod` quando necessária, fiação e pull-up; não interpretar `NORMAL` como leitura segura |
| Aviso `RPi.GPIO não encontrado` | Runtime pode ter caído em GPIO simulado; revisar instalação e compatibilidade antes de validar atuadores |
| Erro `unexpected keyword argument` ou `NameError` após atualizar o Pi | Sincronizar todos os arquivos do runtime para uma versão coerente, não copiar somente um módulo |
| Câmera afeta o DHT22 mesmo após a atualização | Comparar logs com câmera desconectada e conectada; verificar alimentação, GND, USB, cabos e driver. A sequencialização reduz uma fonte de concorrência, mas não prova nem elimina outras causas |
| Reset não libera `EMERGENCY` | Destravar primeiro o botão de emergência e pressionar reset; qualquer risco crítico ativo mantém a emergência travada |

## 14. Checklist de validação

- [ ] Raspberry Pi OS confirmado como 64-bit e acesso SSH funcional
- [ ] Ambiente virtual ativado e dependências instaladas
- [ ] Mosquitto ativo e teste simulado concluído
- [ ] GPIO real confirmado (sem fallback para mock)
- [ ] DHT22 apresenta valores válidos e idade coerente
- [ ] Botões e buzzer testados com segurança
- [ ] PS3 Eye testada localmente
- [ ] Runtime sem IA transmite vídeo sem piora inaceitável da leitura dos sensores
- [ ] Túnel MQTT/câmera e dashboard conectados com tokens correspondentes
- [ ] Modelos ONNX validados antes de habilitar inferência visual

Consulte também [README.md](../README.md), [MATERIAIS_E_MONTAGEM.md](./MATERIAIS_E_MONTAGEM.md) e [STATUS_PROJETO.md](./STATUS_PROJETO.md).
