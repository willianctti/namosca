# Frontend NaMosca

Frontend estático da fase real Axobug.

Ele envia estímulos para o backend, mostra a resposta neural e transforma
`drive.walk`, `drive.escape`, `drive.proboscis`, `drive.wing` e `drive.turn`
em animações da mosca 3D.

## Executar

```bash
cd frontend
python3 -m http.server 8080
```

Abra `http://localhost:8080` com o backend em `http://localhost:8000`.

## Modos

- **FlyWire local** carrega a sub-rede FAFB v783, mostra os pontos dos somas e
  as conexões, e executa o LIF sem chamar a Axobug;
- **Axobug comparação** mantém os experimentos de estímulo e o Shadow Run
  existentes;
- os spikes do LIF local são destacados em amarelo durante a reprodução dos
  frames e permanecem visíveis até a limpeza da cena;
- candidatos `Dm`/descendentes são marcados em laranja e a interface mostra
  quantos deles receberam spike;
- a interface também calcula quantos Dm são topologicamente alcançáveis e a
  distância mínima em sinapses;
- o botão `Mostrar caminhos até Dm` destaca até três caminhos curtos no grafo;
- o seletor de população permite comparar entradas `Pm`, `LMa`, `Tm`, `Dm`,
  `MeMe` e neurônios sem tipo;
- `Dm` funciona como controle direto de entrada, não como prova de um
  estímulo sensorial;
- o botão de limpeza remove os destaques e o gráfico de frames.

A entrada inicial do LIF local é exploratória: ela usa os primeiros
neurônios de maior grau da sub-rede e ainda não representa um estímulo
sensorial validado.

A animação Axobug representa o comando devolvido pelo modelo; não é uma
validação comportamental de uma mosca real.

## Próxima etapa

A sub-rede FAFB v783 já é preparada e carregada pelo backend. O próximo
passo é adicionar um modo separado neste frontend para exibir neurônios,
coordenadas, sinapses e spikes individuais do LIF local.
