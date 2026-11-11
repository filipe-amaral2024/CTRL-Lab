# Materiais e plano de montagem do CTRL-Lab

## 1. Câmera do projeto

O projeto utilizará somente uma **PS3 Eye conectada por USB ao Raspberry Pi**. Ela fornece cada frame aos dois modelos de IA: o modelo de segurança, que fica sempre ativo, e o modelo de acesso/EPI, que pode ser alternado durante a execução.

A câmera de celular via IP foi descartada por apresentar latência e travamentos. Não é necessário instalar aplicativo de streaming nem manter os celulares na rede para a captura.

---

## 2. Lista de materiais recomendados

### 2.1 Raspberry Pi

- Raspberry Pi 3B+ ou 4
- Câmera PS3 Eye USB
- MicroSD 32 GB
- Fonte 5V 3A
- Case do Raspberry
- Cabo microSD
- Cabo HDMI opcional
- Teclado e mouse opcionais

### 2.2 Componentes eletrônicos básicos

- Protoboard
- Jumpers macho-fêmea e fêmea-fêmea
- Resistores para pull-up do DHT22 e divisor de tensão do MQ-2, quando necessário
- Buzzer
- DHT22 (temperatura e umidade)
- Sensor MQ-2 ou MQ-135 (gás/fumaça)
- Botão de emergência
- Fios de conexão

### 2.3 Componentes opcionais

- Módulo ADC para sensor analógico

---

## 3. Materiais mínimos para protótipo funcional

Se a intenção for começar com um protótipo simples e funcional, a lista mínima é:

- 1 Raspberry Pi 3B+
- 1 câmera PS3 Eye USB
- 1 microSD 32 GB
- 1 fonte 5V 3A
- 1 breadboard
- 1 buzzer
- 1 DHT22
- jumpers

Essa configuração já permite validar:

- monitoramento ambiental de temperatura e umidade
- lógica de alertas
- comunicação com o computador central
- estado no dashboard e buzzer reservado para emergências

MQ-2 e botões são opcionais. O runtime oferece suporte ao MQ-2 por saída digital DO, botão de emergência e botão de reset; não lê saída analógica nem calcula concentração em ppm. Os LEDs montados não são mais usados pelo software e podem permanecer desconectados.

---

## 4. Plano de montagem recomendando para o protótipo

### Etapa 1 — Montar alimentação e referência

- Conectar Raspberry Pi à fonte correta.
- Conectar protoboard ao GND e à alimentação 5V.
- Garantir que a massa comum esteja organizada.

### Etapa 2 — Montar buzzer

- O único sinalizador sonoro do protótipo é o buzzer no GPIO23.
- O buzzer toca somente durante EMERGENCY; WARNING/ALERT são indicados visualmente e pelo dashboard.
- Use um driver se o buzzer exigir mais corrente; não alimente carga de alta corrente diretamente pelo GPIO.

### Etapa 3 — Montar o DHT22

- VCC -> 3,3 V (confirme a especificação do sensor/módulo)
- GND -> GND
- DATA -> GPIO17
- Olhando a grade do DHT22 de frente e os pinos para baixo: pino 1 -> VCC, pino 2 -> DATA, pino 3 -> sem conexão, pino 4 -> GND.
- No DHT22 sem módulo, use resistor pull-up de aproximadamente 4,7 kΩ entre DATA e 3,3 V. Módulos prontos podem já incluir esse resistor.

Esse sensor permite medir:

- temperatura
- umidade

O runtime só usa leituras simuladas quando executado com `--mock`. No modo real, se a biblioteca ou o sensor não estiver disponível, os valores serão publicados como `null` e aparecerão como `—` no dashboard.

### Etapa 4 — Montar o sensor de gás

- MQ-2 ou MQ-135 conforme disponibilidade
- VCC -> 5V
- GND -> GND
- DO -> GPIO5 (BCM), usando adaptação de nível para garantir no máximo 3,3 V no GPIO

Para um módulo cuja saída DO possa chegar a 5 V, use um divisor resistivo, por exemplo: DO -> resistor de 10 kΩ -> GPIO5; GPIO5 -> resistor de 15 kΩ -> GND. Una os GNDs do módulo e do Raspberry Pi. Um conversor de nível lógico apropriado também pode ser usado.

**Não conecte OUT diretamente a um GPIO.** O Raspberry Pi não tem entrada analógica, e a saída digital de alguns módulos alimentados em 5 V também pode exceder os 3,3 V tolerados pelos GPIOs. A leitura analógica exige um ADC compatível e a leitura digital exige confirmar a tensão de saída e usar adaptação de nível quando necessário.

O runtime usa somente a saída digital DO e a indica como `Detectado`/`Normal`; isso representa o limiar do comparador ajustado no módulo, não uma concentração em ppm. O padrão é saída ativa em LOW; use `--mq2-active-high` se o seu módulo indicar detecção em HIGH. Confirme no próprio módulo e meça a saída antes de conectar.

### Etapa 5 — Botões de emergência e reset

- Botão normalmente aberto entre GPIO6 (BCM) e GND; o runtime configura pull-up interno.
- Botão normalmente aberto de reset entre GPIO13 (BCM) e GND; o runtime configura pull-up interno.
- O botão de emergência é do tipo trava: ao acioná-lo, o contato permanece ativo até destravar mecanicamente o próprio botão, conforme o modelo instalado.
- Depois de destravar mecanicamente o botão de emergência, pressione o botão separado de reset. Com um modelo visual configurado, a visão é reativada e precisa produzir uma inferência válida; se somente pessoa/jaleco estiver configurado, isso não confirma ausência visual de fogo/fumaça. EMERGENCY só é liberado quando o contato de emergência está inativo e não há condição crítica nos sinais que estão de fato configurados.
- A solicitação de reset permanece pendente até concluir a verificação, mesmo se o botão for solto.
- Durante EMERGENCY, câmera/visão e saídas ficam pausadas; Raspberry Pi, sensores, botões e MQTT/status permanecem ativos para permitir reset e acompanhar o estado.
- Não conecte o botão a 3,3 V ou 5 V.

Essa pausa é uma ação de software; não desliga a alimentação do Raspberry Pi nem substitui uma parada de emergência elétrica/certificada para equipamentos de potência.

---

## 5. Estrutura lógica da montagem

```text
PS3 Eye (USB) ── Raspberry Pi (captura de frame + dois modelos)
                           │
                           └── MQTT ── Computador (interface/histórico)

Computador:
- Dashboard futuro; alterna somente o modelo de acesso via MQTT
- Recepção de eventos via MQTT
- Histórico SQLite

Raspberry Pi:
- Uma captura por ciclo da PS3 Eye
- Modelo de pessoa/jaleco, executável sem o modelo visual de segurança
- Modelo visual de fogo/fumaça opcional
- DHT22
- MQ-2 pela saída digital DO (sem leitura em ppm)
- buzzer
- botão de emergência e botão de reset
- status e eventos via MQTT
```

---

### Execução do modelo no Pi

Conecte a PS3 Eye ao Pi e confirme o índice de dispositivo (padrão `0`). Copie os modelos ONNX para o Pi. Instale apenas as dependências Python de [requirements.txt](../requirements.txt); não é necessário instalar Ultralytics nem PyTorch para inferência. Ultralytics pode ser usado em outro computador apenas para exportar os modelos YOLOv8 em ONNX com `imgsz=320`.

Para validar a pré-visualização da câmera no dashboard sem modelo de IA, configure `CTRL_LAB_CAMERA_TOKEN` com um segredo de pelo menos 16 caracteres e execute `python -m raspberry_pi.main --broker localhost --camera-device 0 --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN" --camera-stream-host 127.0.0.1`. Esse modo configura a imagem para 640x480 (VGA, 4:3) e um alvo de até 24 FPS, com captura/codificação síncrona para não executar uma thread de captura concorrente com as leituras dos sensores. O driver pode não aceitar exatamente a resolução ou a taxa solicitadas; a captura/codificação pode reduzir a cadência efetiva e atrasar o loop. 24 FPS aumenta o uso de CPU e USB e pode afetar o timing ou a estabilidade do DHT22, portanto valide os logs de idade/falhas do sensor no Raspberry. O loop de controle roda a 48 Hz; o DHT22 é consultado a cada 5 s por padrão (mínimo efetivo de 2 s), e a última leitura válida é mantida por até 12 s. O intervalo maior reduz as leituras do DHT22, mas não reduz diretamente o trabalho da câmera. O MQ-2 e os botões continuam sendo verificados a 48 Hz. O log/status MQTT é atualizado a cada segundo. Após 12 s sem leitura válida, temperatura e umidade ficam indisponíveis e a idade da leitura é informada. A execução sequencial não fornece garantias de tempo real e não exclui problemas elétricos, de USB ou de escalonamento do Linux. Esse modo não detecta fumaça/fogo. O stream para durante EMERGENCY e retorna após o reset. Com o servidor vinculado a `127.0.0.1`, use no PC um túnel SSH adicional para a porta `8081`; configure o dashboard com o mesmo token e URL `http://127.0.0.1:8081/video.mjpg`.

Para a apresentação focada em jaleco, use somente o detector de acesso:

```bash
python3 -m raspberry_pi.main \
  --broker localhost \
  --camera-device 0 \
  --access-model models/ctrlab-access.onnx \
  --access-classes person_with_labcoat,person_without_labcoat \
  --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN" \
  --camera-stream-host 127.0.0.1
```

O modelo pode fornecer as classes `person_with_labcoat,person_without_labcoat` na ordem correta, ou o perfil legado `person,lab_coat`, e deve gerar saída YOLOv8 ONNX de detecção compatível com OpenCV DNN. Para o primeiro perfil, cada pessoa detectada é avaliada diretamente pela classe: com jaleco é permitida; sem jaleco gera alerta. O modelo começa habilitado; `A` ou o botão do dashboard pode pausar/reativar a análise. O detector visual de fogo/fumaça pode ser adicionado depois com `--safety-model` e `--safety-classes smoke,fire`; ele não é requisito para iniciar o detector de jaleco. Os sensores físicos configurados no software permanecem independentes. O repositório fornece conversor de polígonos para caixas YOLO, mas não inclui pesos treinados. O MQTT publica resultados e estado no tópico `ctrlab/raspberry/status`.

### Acesso ao dashboard pela rede local

Execute o dashboard no computador que receberá os status MQTT. No PowerShell:

```powershell
pip install -r requirements.txt
$env:CTRL_LAB_DASHBOARD_TOKEN = "use-um-token-aleatorio-com-16-caracteres-ou-mais"
python -m central.dashboard --host 0.0.0.0 --port 8000 --broker <IP_DO_RASPBERRY>
```

No navegador de qualquer dispositivo na mesma rede, abra `http://<IP_DO_COMPUTADOR>:8000` e informe o token. O dashboard mostra estado, sensores, resultados da visão e eventos recentes. O botão remoto apenas alterna o modelo de pessoa/jaleco; sinais físicos de risco permanecem independentes. O status é atualizado via MQTT. A pré-visualização MJPEG pode ser habilitada com token e túnel SSH conforme o [guia de execução](./GUIA_EXECUCAO.md).

Libere a porta TCP 8000 no firewall do computador anfitrião para a rede local e garanta que o broker MQTT no Raspberry aceite conexões dessa rede. Não exponha o dashboard ou o broker diretamente à Internet: a interface usa HTTP sem criptografia e deve permanecer em uma rede confiável.

## 6. Ordem recomendada de montagem

1. Montar Raspberry com o buzzer.
2. Validar GPIO e estado pelo dashboard.
3. Integrar DHT22 e testar temperatura/umidade.
4. Validar comunicação MQTT.
5. Conectar a PS3 Eye e validar a captura local.
6. Copiar os modelos ONNX e validar a segurança contínua e, se houver modelo compatível, a alternância do acesso.
7. Configurar o broker, iniciar o dashboard web e conectar status/comandos MQTT.
8. Validar o limiar digital do MQ-2 e confirmar a tensão do DO com multímetro antes de conectar.
9. Validar que o botão de emergência trava EMERGENCY e que o reset só funciona sem risco crítico ativo.

---

## 7. Dicas de projeto para apresentação

- Use a PS3 Eye fixa, enquadrando a área de acesso e a área que precisa de monitoramento de segurança.
- Confirme que desligar o modelo de acesso não interrompe o modelo de segurança.
- Faça a montagem em protoboard, fácil de demonstrar.
- Use o dashboard para acompanhar os estados; o buzzer toca somente em EMERGENCY.
- Mostre a transição entre NORMAL, ALERTA e EMERGÊNCIA.
- Simule cenários como:
  - pessoa sem jaleco
  - fumaça detectada
  - temperatura alta
  - gás acima do limite

---

## 8. Checklist final antes da apresentação

- [ ] PS3 Eye detectada e estável no Raspberry Pi
- [ ] modelo de segurança executando continuamente
- [ ] atalho `A` alternando o modelo de acesso
- [ ] comando MQTT alternando o modelo de acesso
- [ ] Raspberry lendo sensores
- [ ] buzzer funcionando
- [ ] MQTT funcionando
- [ ] dashboard acessível pelo IP do computador anfitrião
- [ ] token configurado e controle remoto de acesso validado
- [ ] lógica de risco validada
- [ ] apresentação preparada com cenários reais

---

## 9. Recomendação final

Para reduzir latência e consumo de recursos:

- usar somente uma câmera PS3 Eye USB para os dois modelos
- manter a inferência do modelo de acesso desligada quando não for necessária
- montar protótipo com DHT22 + MQ-2 + buzzer
- validar primeiro a parte eletrônica e de comunicação
- medir desempenho dos modelos na resolução configurada

Esse caminho é simples, barato e bem adequado ao escopo acadêmico do projeto.
