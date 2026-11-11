# Pendências para concluir o CTRL-Lab

Este checklist traduz o estado do código em trabalho verificável para chegar a uma demonstração integrada. “Implementado” significa que existe lógica/teste de software; não significa que o comportamento foi validado no Raspberry, nos sensores físicos ou com modelos treinados.

## Estado resumido

- [x] Estrutura Python modular, runtime Raspberry, dashboard e persistência SQLite.
- [x] Estados de alerta, controle do buzzer e lógica de botão de emergência/reset.
- [x] Suporte a DHT22, entrada digital de gás, câmera USB e stream MJPEG protegido.
- [x] Infraestrutura de inferência OpenCV DNN para modelos YOLOv8 ONNX.
- [x] Modo de inferência pessoa/jaleco sem exigir o modelo visual de fogo/fumaça.
- [x] Avaliação visual focada somente em jaleco; associação no perfil legado e classe direta pessoa-com/sem-jaleco no perfil novo.
- [x] Inicializador Windows aceita `-AccessModel` e transfere o ONNX para o Pi.
- [x] Testes automatizados locais dos componentes principais; última suíte executada: 97 testes aprovados.
- [ ] Modelos treinados/validados incluídos ou fornecidos para inferência real.
- [ ] Deploy concluído no Raspberry acessível e teste integrado de ponta a ponta.
- [ ] Medições e critérios de aceitação definidos para desempenho e qualidade de detecção.
- [ ] Fiação e comportamento físico dos sensores/atuadores confirmados.

## Prioridade 0 — Desbloquear o Raspberry e comprovar o fluxo básico

### 1. Restabelecer a conexão PC–Pi

- [ ] Confirmar que PC e Raspberry estão na mesma rede ou possuem rota entre si.
- [ ] Encontrar o IP atual do Pi no roteador ou no próprio Pi; não presumir que o endereço salvo continua válido.
- [ ] Confirmar SSH na porta 22 com `Test-NetConnection <IP-ATUAL> -Port 22`.
- [ ] Iniciar com `.\start-ctrlab.ps1 -RaspberryHost <IP-ATUAL>` quando o endereço padrão não for válido.
- [ ] Resolver erros de autenticação somente depois de a porta SSH estar alcançável.

**Critério de aceite:** sincronização, instalação/verificação de dependências e inicialização remota terminam sem erro; o Pi registra o PID e o log do runtime.

> O último log reportado nesta conversa falhou com timeout para `192.168.15.75`. Um timeout de porta 22 é problema de conectividade/IP, anterior à autenticação SSH. O inicializador padrão usa esse endereço até receber outro por parâmetro.

### 2. Validar o modo de pré-visualização sem IA

- [ ] Confirmar que a PS3 Eye aparece no Pi e que o índice de dispositivo é o esperado.
- [ ] Rodar o teste isolado `python -m raspberry_pi.main --camera-test --camera-device 0 --camera-test-frames 30`.
- [ ] Iniciar o modo padrão, verificar o MJPEG no dashboard e observar os logs de câmera.
- [ ] Medir FPS e resolução no runtime completo; não aceitar o valor solicitado de 24 FPS como prova do valor efetivo.
- [ ] Observar CPU, memória, temperatura do Pi e estabilidade do DHT22 com a câmera em uso.
- [ ] Comparar Wi-Fi com Ethernet se houver travamentos de transmissão; separar problemas de rede de problemas de captura/codificação no Pi.

**Critério de aceite:** câmera permanece aberta pelo período de teste, stream é acessível pelo túnel, taxa/resolução reais estão registradas e não há falhas inaceitáveis no loop de sensores.

### 3. Confirmar sensores e GPIO reais

- [ ] Validar DHT22 no GPIO17, incluindo alimentação, GND comum e resistor pull-up quando necessário.
- [ ] Validar leitura e idade DHT22 com o intervalo padrão de 5 s e expiração após 12 s sem sucesso.
- [ ] Validar a polaridade e o nível elétrico da saída DO do MQ-2 no GPIO5; adaptar qualquer sinal acima de 3,3 V.
- [ ] Validar botões de emergência/reset nos GPIO6/GPIO13 e debounce em circuito real.
- [ ] Validar buzzer no GPIO23 com driver adequado quando necessário.
- [ ] Confirmar no log que `RPi.GPIO` real foi carregado; tratar fallback para modo mock como falha de configuração de hardware.
- [ ] Executar testes individuais e registrar leituras/estados, inclusive perda de sensor e recuperação.

**Critério de aceite:** cada periférico é identificado individualmente, e o estado mostrado no dashboard coincide com medições e acionamentos físicos esperados. Não conectar sinal de 5 V diretamente a GPIO.

### 4. Validar MQTT e dashboard no fluxo automatizado

- [ ] Confirmar Mosquitto ativo no Pi, conexão MQTT pelo túnel e recebimento de status a cada segundo.
- [ ] Confirmar que os valores `null` aparecem como indisponíveis, em vez de parecerem leituras válidas.
- [ ] Confirmar o proxy MJPEG pelo dashboard e a rejeição de token inválido.
- [ ] Confirmar tokens para controle e câmera, e que o botão do dashboard relata claramente falha ou falta de confirmação.
- [ ] Verificar se status normal não polui excessivamente o histórico SQLite (ver prioridade 2).

**Critério de aceite:** um ensaio contínuo do início ao fim apresenta status recente, vídeo e dados de sensor; os erros de rede/serviço são identificáveis sem confundi-los com detecção normal.

## Prioridade 1 — Tornar a visão computacional funcional

### 5. Obter e validar o modelo de pessoa/jaleco

- [x] Adicionar localmente o dataset Lab Coat Detection 3 v12 (CC BY 4.0) com classes `person_with_labcoat` e `person_without_labcoat`.
- [x] Criar conversor que preserva a origem e transforma as segmentações poligonais em caixas YOLO para detecção.
- [x] Adaptar o avaliador e os inicializadores para aceitar as duas classes de status por pessoa, mantendo o perfil legado `person,lab_coat`.
- [ ] Inspecionar visualmente amostras e confirmar a semântica/qualidade das anotações, inclusive no enquadramento da PS3 Eye.
- [ ] Treinar um detector YOLOv8 com o conjunto convertido; verificar as licenças de treinamento, modelo inicial e pesos redistribuídos.
- [ ] Avaliar no split `test` precisão/recall por classe, matriz de confusão, falsos alertas e pessoas sem jaleco incorretamente permitidas.
- [ ] Confirmar ordem das classes `person_with_labcoat,person_without_labcoat`, dimensões da entrada e compatibilidade ONNX com `OpenCVDNNYOLODetector`.
- [ ] Validar latência, limiar de confiança, enquadramento, ângulo, distância e iluminação da demonstração.
- [ ] Treinar/exportar um modelo visual separado de fogo/fumaça somente se houver tempo e dados adequados; sensores físicos continuam como camada separada.
- [ ] Versionar ou distribuir os pesos por canal documentado; não os inserir no repositório sem conferir tamanho, licença e política de distribuição.
- [ ] Testar precisão/recall, falsos positivos e falsos negativos com cenas e iluminação reais. Uma imagem de demonstração não basta como validação.

**Critério de aceite:** um ONNX de pessoa/jaleco identificado por versão e checksum carrega no Pi, e a avaliação documenta acertos e erros no teste reservado e em cenas representativas da apresentação.

### 6. Integrar a inferência no Raspberry

- [ ] Iniciar pessoa/jaleco sozinho com `--access-model <arquivo.onnx>` ou `.\start-ctrlab.ps1 -AccessModel <arquivo.onnx>`.
- [ ] Confirmar que o modelo de jaleco começa habilitado no modo de modelo único.
- [ ] Validar alternância do acesso por tecla `A` em terminal interativo e pelo comando autenticado no dashboard.
- [ ] Confirmar que o status visual de fogo/fumaça aparece como não configurado, sem afetar os sensores físicos.
- [ ] Verificar serialização de detecções, estado visual, latência e comportamento quando arquivo/modelo está ausente ou inválido.
- [ ] Medir duração real de cada inferência, ciclos efetivos, uso de CPU/memória e estabilidade térmica/USB sob carga.
- [ ] Medir no Raspberry a cadência efetiva do padrão de inferência de 1 s e a estabilidade da votação por janelas de 5 s; o tempo do modelo pode alongar os ciclos.
- [ ] Avaliar o custo da prévia junto com a inferência e ajustar captura, qualidade JPEG ou intervalo com medições, sem pressupor que 24 FPS seja sustentável.

**Critério de aceite:** o detector de jaleco produz resultados consistentes em cenários definidos; inferência não degrada o loop de sensores além dos limites acordados; adicionar ou alternar o modelo de acesso não interfere nos sinais físicos de risco.

## Prioridade 2 — Fechar lógica de segurança e produto

### 7. Ensaiar a máquina de estados e emergência

- [ ] Validar `NORMAL`, `WARNING`, `ALERT` e `EMERGENCY` com entradas físicas e visuais controladas.
- [ ] Testar travamento de emergência, liberação mecânica, reset e confirmação visual segura.
- [ ] Confirmar comportamento se o detector falhar, a câmera desconectar, MQTT cair ou leitura do sensor expirar.
- [ ] Verificar se sensores físicos dedicados de chama/fumaça estão conectados ao software; no runtime atual só a entrada digital do MQ-2 está configurada como sinal de gás/limiar.
- [ ] Decidir a política para estado normal quando o dado ambiental está indisponível: indisponível não deve ser interpretado como condição comprovadamente segura.
- [ ] Documentar limites, avisos e procedimentos operacionais.

**Critério de aceite:** cada cenário tem resultado esperado, log e status MQTT verificáveis; perda de sensores/visão é apresentada como falha ou indisponibilidade, não como detecção normal confiável.

> A emergência atual é lógica de software. O projeto não é um sistema certificado de segurança e não deve ser usado para controlar equipamento de potência sem um circuito de segurança independente projetado para esse fim.

### 8. Separar telemetria de eventos

- [ ] Alterar ou especificar o armazenamento central para não criar um evento de histórico para cada status periódico normal.
- [ ] Persistir eventos quando ocorrer transição de estado, alarme, mudança de acesso ou falha relevante; manter telemetria atual separada, se necessária.
- [ ] Definir retenção, limite de crescimento e exportação/backup do SQLite.
- [ ] Validar classificação e detalhes dos eventos produzidos por sensores e visão.

**Critério de aceite:** uma execução normal longa não cria centenas de ocorrências idênticas por hora, enquanto incidentes e transições continuam consultáveis.

### 9. Rever comunicação e segurança operacional

- [ ] Confirmar em qual interface o Mosquitto escuta e manter o broker indisponível a redes não confiáveis.
- [ ] Manter MQTT e vídeo no túnel SSH quando não houver autenticação/TLS configurados.
- [ ] Gerar, armazenar, trocar e invalidar tokens com procedimento documentado; não compartilhar tokens em logs, commits ou apresentações.
- [ ] Definir interface/porta do dashboard para a demonstração e restringir o acesso conforme a rede.
- [ ] Revisar dependências e instalação repetível do Pi; confirmar que modo mock/fallback não é confundido com operação física.
- [ ] Rever a distribuição de chaves SSH privadas e proteger a conta Windows que as guarda.

**Critério de aceite:** superfície de rede, autenticação e procedimento de acesso são conhecidos pela equipe; uma rede externa não consegue acessar controles ou stream sem autorização.

## Prioridade 3 — Preparar demonstração e entrega

### 10. Executar ensaio final e registrar evidências

- [ ] Fazer ensaio no mesmo Pi, câmera, iluminação, distância e montagem que serão usados na apresentação.
- [ ] Registrar FPS efetivo, resolução, latência de vídeo, latência/cadência de inferência, CPU/RAM, temperatura e leituras/falhas DHT22.
- [ ] Demonstrar um caso normal, um alerta ambiental, uma emergência, reset e ativação/desativação do acesso.
- [ ] Preparar conjunto de imagens/clipes de teste e resultados esperados para repetir a demonstração.
- [ ] Documentar versões do Pi OS, Python, OpenCV, dependências, modelos, parâmetros, cabeamento e IP/rede necessários.
- [ ] Definir plano de contingência sem rede ou sem câmera, deixando explícito o que ainda pode ser demonstrado.
- [ ] Rodar a suíte automatizada final após as últimas alterações e registrar o resultado.

**Critério de aceite:** outra pessoa da equipe consegue instalar, iniciar, validar e encerrar a demonstração seguindo a documentação, e os resultados observados são reproduzíveis.

## Ordem recomendada de execução

1. Corrigir conectividade e fazer deploy do modo sem IA.
2. Validar a câmera, os sensores e o circuito um componente por vez.
3. Validar MQTT, dashboard, tokens e stream pelo túnel.
4. Treinar/exportar e testar os modelos.
5. Integrar modelos e medir desempenho do Pi sob carga real.
6. Ensaiar alarmes, emergência/reset, falhas e política de indisponibilidade.
7. Separar eventos de telemetria e fechar a revisão operacional.
8. Fazer o ensaio completo e registrar evidências para a apresentação.

## Referências

- [Funcionamento atual](./FUNCIONAMENTO_ATUAL.md)
- [Guia passo a passo](./GUIA_EXECUCAO.md)
- [Materiais e montagem](./MATERIAIS_E_MONTAGEM.md)
- [Plano de desenvolvimento original](../PLANO_DESENVOLVIMENTO.md)
