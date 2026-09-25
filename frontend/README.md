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

## Modo experimental

- `food` pode iniciar a caminhada;
- `loom` controla a resposta de escape;
- `Shadow Run` executa uma corrida com cinco sombras;
- o painel de resposta pode ser aberto no canto superior direito;
- a explicação da simulação pode ser minimizada no canto inferior direito.

A animação representa o comando devolvido pelo modelo; não é uma validação
comportamental de uma mosca real.

## Próxima etapa

A sub-rede FAFB v783 já é preparada e carregada pelo backend. O próximo
passo é adicionar um modo separado neste frontend para exibir neurônios,
coordenadas, sinapses e spikes individuais do LIF local.
