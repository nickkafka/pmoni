# Prever — Dark Gold Design System

Contexto de design extraído do app **Prever Proposta**. Este documento é
autossuficiente: contém todos os tokens, padrões de componente e regras
necessárias para reproduzir a mesma identidade visual em outro sistema,
sem depender do código original.

Stack de referência: React + TypeScript, estilos inline (`style={{}}`) com
tokens em CSS custom properties. Os padrões abaixo funcionam igualmente em
Tailwind, CSS-in-JS ou CSS puro — o que importa são os valores.

---

## 1. Identidade

**Dark-first, dourado como único acento.** Fundo quase preto com brilho
radial, superfícies elevadas em degradê sutil, e um dourado (`#FFC000`)
que carrega toda a hierarquia de ação. Referências estéticas: Robinhood,
Linear, Vercel Dashboard.

Princípios que governam as decisões:

1. **Um acento só.** Dourado é ação, destaque e identidade. Nunca introduza
   uma segunda cor de marca; cores adicionais existem apenas como status
   semântico (sucesso/erro/info).
2. **Superfícies em degradê, nunca chapadas.** Todo card usa gradiente de
   160° no escuro e 135° no claro — dá profundidade sem sombra pesada.
3. **Tipografia com peso, não com tamanho.** Montserrat SemiBold/Bold para
   títulos; hierarquia vem de peso, `letter-spacing` e maiúsculas.
4. **Rótulos em caixa alta espaçada.** Toda seção é anunciada por um micro-label
   de 10–11px, `letter-spacing` largo, maiúsculo — é a assinatura do sistema.
5. **Dois temas de verdade.** Claro não é o escuro invertido: é um conjunto
   próprio de valores. Nenhum componente pode ter cor fixa fora de um branch
   de tema (ver §8, o erro mais comum).

---

## 2. Tokens de cor

### 2.1 Dourado (acento único)

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `gold-primary` | `#FFC000` | `#b87800` | Ícones, textos de destaque, bordas ativas |
| `gold-bright` | `#FFD340` | `#d99000` | Realce, glow |
| `gold-dim` | `#B88A00` | `#7a5000` | Texto dourado secundário |
| `gold-glow` | `rgba(255,192,0,0.18)` | `rgba(184,120,0,0.10)` | Fundo de chip/badge ativo |

> **Regra crítica:** no modo claro o dourado **escurece** para `#b87800`.
> `#FFC000` sobre branco tem contraste ~1.9:1 — ilegível. Nunca use o dourado
> do escuro em fundo claro para texto ou ícone.

**Gradiente dourado (CTA primário)** — idêntico nos dois temas:

```css
background: linear-gradient(135deg, #FFD700, #FFC000, #FF9F00);
color: #08090E;                                  /* SEMPRE texto escuro */
box-shadow: 0 6px 20px rgba(255,192,0,0.35);
```

> Texto **branco** sobre esse gradiente dá ~2:1 de contraste. O par correto é
> sempre `#08090E` / `#0A0A0A`, nos dois temas.

### 2.2 Superfícies

| Token | Escuro | Claro |
|---|---|---|
| `bg-base` (página) | `#08090E` | `#f4f5f7` |
| `bg-elevated` (card) | `#0F111A` | `#ffffff` |
| `bg-overlay` (popover/modal) | `#161926` | `#e8eaee` |
| `card-gradient` | `linear-gradient(160deg, #14141b 0%, #0b0b10 100%)` | `linear-gradient(135deg, #ffffff 0%, #f5f6f8 100%)` |
| `card-border` | `1px solid rgba(255,192,0,0.10)` | `1px solid rgba(0,0,0,0.07)` |
| `card-shadow` | `none` (ou glow) | `0 1px 6px rgba(0,0,0,0.07)` |
| `input-bg` | `linear-gradient(160deg, #14141b 0%, #0b0b10 100%)` | `#ffffff` |
| `input-border` | `1px solid rgba(255,255,255,0.10)` | `1px solid rgba(0,0,0,0.12)` |

### 2.3 Texto e ícone

| Token | Escuro | Claro |
|---|---|---|
| `text-primary` | `#ffffff` | `#0a0b0e` |
| `text-secondary` | `rgba(255,255,255,0.55)` | `#4a5060` |
| `text-muted` | `rgba(255,255,255,0.40)` | `#8a909e` |
| `text-on-gold` | `#08090E` | `#08090E` |
| `label-caps` (micro-label) | `rgba(255,192,0,0.65)` | `rgba(0,0,0,0.55)` |
| `border-subtle` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.07)` |
| `divider` | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.07)` |
| `placeholder` | herda `text-muted` | `rgba(0,0,0,0.35)` |

### 2.4 Status semântico

Cada status tem trio `color` / `bg` / `border`. O `bg` é sempre a cor a 12%
e a `border` a 30% — mantenha essa proporção ao criar novos status.

| Status | Cor (escuro) | Cor (claro) | bg | border |
|---|---|---|---|---|
| Pendente / aviso | `#FFC000` | `#b87800` | `rgba(255,192,0,0.12)` | `rgba(255,192,0,0.30)` |
| Info / em análise | `#60A5FA` | `#1d4ed8` | `rgba(96,165,250,0.12)` | `rgba(96,165,250,0.30)` |
| Sucesso / aprovado | `#34D399` | `#047857` | `rgba(52,211,153,0.12)` | `rgba(52,211,153,0.30)` |
| Erro / reprovado | `#F87171` | `#b91c1c` | `rgba(248,113,113,0.12)` | `rgba(248,113,113,0.30)` |
| Neutro / vazio | `#9ca3af` | `#6b7280` | `rgba(156,163,175,0.10)` | `rgba(156,163,175,0.25)` |

> Status **nunca** é comunicado só por cor: sempre acompanha ícone + rótulo.

### 2.5 Botão de sucesso (confirmar/aprovar)

Verde sólido com brilho, usado para a ação de confirmação final:

```css
background: linear-gradient(135deg, #34D399 0%, #10B981 40%, #059669 100%);
color: #FFFFFF;
box-shadow: 0 4px 20px rgba(16,185,129,0.45),
            inset 0 0 0 1px rgba(110,231,183,0.35),
            inset 0 1px 0 rgba(255,255,255,0.20);
text-shadow: 0 1px 3px rgba(0,0,0,0.35);
```

---

## 3. Tipografia

**Família:** `"Montserrat", "Inter", ui-sans-serif, system-ui, sans-serif`
Pesos carregados: 200, 300, 400, 500, 600, 700.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@200;300;400;500;600;700&display=swap" rel="stylesheet">
```

| Papel | Tamanho | Peso | Extras |
|---|---|---|---|
| Título de página | 22px | 600 | `letter-spacing: -0.02em` |
| Título de tela/header | 18px | 600 | `letter-spacing: 0.02em` |
| Título de card | 16px | 600 | — |
| **Micro-label de seção** | **10–11px** | **700** | `letter-spacing: 0.12–0.18em`, `text-transform: uppercase` |
| Corpo | 13–14px | 300–500 | — |
| Corpo secundário | 12px | 300 | cor `text-secondary` |
| Legenda/observação | 10–11px | 300 | cor `text-muted` |
| **Label de botão CTA** | **13px** | **700** | `letter-spacing: 0.16–0.18em`, `uppercase` |
| Valor monetário destaque | 20px | 800 | — |

O micro-label maiúsculo é o elemento mais característico do sistema —
use-o para abrir **toda** seção de conteúdo.

---

## 4. Forma, elevação e movimento

| Token | Valor |
|---|---|
| Raio base (`--radius`) | `1rem` (16px) |
| Raio de card | 16–18px |
| Raio de input/botão secundário | 12–14px |
| Raio de CTA (pílula) | 28px (metade da altura 56) |
| Raio de chip/badge | 999px (ou 12px em chips retangulares) |
| Raio de avatar/ícone circular | `50%` |
| Altura de CTA principal | 56px |
| Altura de input | 50–52px |
| Altura de botão secundário | 44–48px |
| Ícone de botão circular | 40×40px (ícone 18px) |
| Padding de card | `16–20px` vertical, `16–18px` horizontal |
| Gap entre cards | 12–16px |
| Gap interno (lista) | 8–10px |

**Transição global** (dá o efeito de troca suave de tema):

```css
*, *::before, *::after {
  transition: background-color 0.35s ease, color 0.35s ease, border-color 0.35s ease;
}
```

Transições de interação: `all 0.15s` em botões/chips, `0.2s` em bordas.

**Textura de ruído** sobre o fundo escuro (sutileza que evita banding):

```css
body::before {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  opacity: 0.025;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.6 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
}
```

---

## 5. Fundos de página

Três fundos, escolhidos por contexto:

**Escuro — gradiente radial base (sempre no `body`):**
```css
background: radial-gradient(ellipse at top center, #131828 0%, #08090E 55%, #05060A 100%);
background-attachment: fixed;
```

**Escuro — constelação animada** (canvas): nós dourados pulsantes conectados
por linhas + polígonos irregulares girando lentamente. Densidade ~38 nós /
1280×800 (20 em telas < 768px), distância de conexão 190px, acento `#FFC000`.
Reserve para telas de entrada (login, home) — é caro em CPU.

**Escuro — versão estática** (SVG): mesma linguagem visual, sem animação —
nós dourados (`radialGradient` de `#ffe27a` → `#e8b923`) sobre
`radial-gradient(ellipse 120% 90% at 30% 20%, #14140f, #0a0a08, #050504, #000)`,
com vinheta `radial-gradient(ellipse 70% 60% at 50% 50%, transparent, rgba(0,0,0,0.45))`.
Use em todas as telas internas.

**Claro:**
```css
background: radial-gradient(ellipse at top, #f7f8fa 0%, #eef0f4 60%, #e4e7ec 100%);
```
Mesma constelação, com acento `#d99000`, linhas `rgba(150,156,165,0.7)` e
vinheta `rgba(0,0,0,0.06)`.

---

## 6. Padrões de componente

Todos os exemplos assumem uma variável booleana `isLight` disponível.

### 6.1 Card (bloco de conteúdo)

```jsx
const CARD = {
  background: isLight
    ? "linear-gradient(135deg,#ffffff 0%,#f5f6f8 100%)"
    : "linear-gradient(160deg, #14141b 0%, #0b0b10 100%)",
  border: isLight ? "1px solid rgba(0,0,0,0.07)" : "1px solid rgba(255,192,0,0.10)",
  borderRadius: 18,
  padding: "20px 18px",
  boxShadow: isLight ? "0 1px 6px rgba(0,0,0,0.07)" : "none",
};
```

Variante "glass" (só no escuro, para sobrepor o fundo animado):
```jsx
background: "rgba(8,8,12,0.22)",
backdropFilter: "blur(24px) saturate(200%)",
```

### 6.2 Micro-label de seção

```jsx
const LABEL = {
  fontFamily: "'Montserrat', sans-serif",
  fontWeight: isLight ? 600 : 300,
  fontSize: 11,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: isLight ? "rgba(0,0,0,0.55)" : "rgba(255,192,0,0.65)",
  marginBottom: 8,
};
```

### 6.3 CTA primário (pílula dourada)

```jsx
const CTA_GOLD = {
  width: "100%", height: 56, borderRadius: 28, border: "none",
  background: "linear-gradient(135deg,#FFD700,#FFC000,#FF9F00)",
  color: "#08090E",                                  // nos DOIS temas
  fontFamily: "'Montserrat', sans-serif",
  fontWeight: 700, fontSize: 13,
  letterSpacing: "0.16em", textTransform: "uppercase",
  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
  boxShadow: "0 6px 20px rgba(255,192,0,0.35)",
  cursor: "pointer",
};
```

Variante outline: `background: transparent`, `color: #F59E0B`,
`border: 1.5px solid #F59E0B`.

### 6.4 Botão de seleção (opção marcável)

O padrão mais usado do app — grid de opções onde a selecionada vira dourada:

```jsx
{
  height: 60, borderRadius: 14,
  border: selected ? "none"
    : isLight ? "1px solid rgba(0,0,0,0.12)" : "1px solid rgba(255,215,0,0.16)",
  background: selected
    ? "linear-gradient(135deg,#FFD700,#FFC000,#FF9F00)"
    : isLight ? "#f5f6f8" : "linear-gradient(160deg, #14141b 0%, #0b0b10 100%)",
  color: selected ? "#08090E" : isLight ? "#0a0b0e" : "#fff",
  boxShadow: selected ? "0 6px 20px rgba(255,192,0,0.35)" : undefined,
  fontWeight: 600, fontSize: 14, textTransform: "uppercase",
  transition: "all 0.15s",
}
```

### 6.5 Input / textarea

```jsx
{
  width: "100%", height: 52, borderRadius: 14, padding: "0 16px",
  background: isLight ? "#ffffff" : "linear-gradient(160deg, #14141b 0%, #0b0b10 100%)",
  border: isLight ? "1px solid rgba(0,0,0,0.12)" : "1px solid rgba(255,255,255,0.10)",
  color: isLight ? "#0a0b0e" : "#fff",
  fontFamily: "'Montserrat', sans-serif", fontWeight: 300, fontSize: 14,
  outline: "none", boxSizing: "border-box",
  colorScheme: isLight ? "light" : "dark",   // obrigatório em date/time
}
```

### 6.6 Chip de status

```jsx
{
  padding: "4px 10px", borderRadius: 12,
  background: status.bg,                    // cor a 12%
  color: isLight ? status.colorDark : status.color,
  fontWeight: 600, fontSize: 10,
  letterSpacing: "0.06em", textTransform: "uppercase",
}
```

### 6.7 Botão circular de voltar (header)

```jsx
{
  width: 40, height: 40, borderRadius: 12,
  background: isLight ? "#ffffff" : "#191921",
  border: isLight ? "1px solid rgba(0,0,0,0.10)" : "1px solid rgba(255,255,255,0.10)",
  color: isLight ? "#0a0b0e" : "#fff",
  display: "flex", alignItems: "center", justifyContent: "center",
  boxShadow: isLight ? "0 1px 3px rgba(0,0,0,0.05)" : undefined,
  cursor: "pointer",
}
```

### 6.8 Header de tela

Botão voltar + título/subtítulo + indicador de passo (barrinhas de 20×4px):

```jsx
<div style={{ display: "flex", alignItems: "center", gap: 12 }}>
  <button style={BACK_BTN}><ArrowLeft size={18} /></button>
  <div style={{ flex: 1, minWidth: 0 }}>
    <div style={{ fontWeight: 600, fontSize: 18 }}>Título</div>
    <div style={{ fontSize: 12, color: textSecondary }}>Subtítulo</div>
  </div>
  <div style={{ display: "flex", gap: 4 }}>
    {[true, false, false].map((active, i) => (
      <div key={i} style={{
        width: 20, height: 4, borderRadius: 2,
        background: active ? gold : isLight ? "rgba(0,0,0,0.12)" : "rgba(255,255,255,0.12)",
      }} />
    ))}
  </div>
</div>
```

### 6.9 Barra de navegação flutuante (mobile)

Pílula centralizada, fixa acima da safe-area:

```jsx
{
  position: "fixed", left: "50%", bottom: "max(16px, env(safe-area-inset-bottom))",
  transform: "translateX(-50%)", zIndex: 50,
  display: "flex", gap: 8, padding: "10px 14px",
  background: isLight ? "#ffffff" : "linear-gradient(160deg, #14141b 0%, #0b0b10 100%)",
  backdropFilter: "blur(30px) saturate(180%)",
  border: isLight ? "1px solid rgba(0,0,0,0.08)" : "1px solid rgba(255,255,255,0.22)",
  borderRadius: 40, minWidth: 220,
  boxShadow: isLight
    ? "0 6px 24px rgba(0,0,0,0.10), 0 0 0 1px rgba(0,0,0,0.03) inset"
    : "0 8px 32px rgba(0,0,0,0.6), 0 0 40px rgba(255,255,255,0.06), 0 0 0 1px rgba(255,255,255,0.04) inset",
}
```

Item ativo: fundo `rgba(184,120,0,0.10)` (claro) / `rgba(255,255,255,0.12)` (escuro),
ícone com `strokeWidth` 2.4 (vs 1.8), ponto de 4px abaixo, e glow
`drop-shadow(0 0 8px …)` apenas no escuro.

### 6.10 Modal / popup

```jsx
// backdrop
{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.60)", zIndex: 90 }

// painel
{
  position: "fixed", left: "50%", top: "50%", transform: "translate(-50%,-50%)",
  width: "min(440px, 92vw)", maxHeight: "86vh", overflowY: "auto", zIndex: 100,
  borderRadius: 18, padding: "20px 18px",
  background: isLight ? "#ffffff" : "linear-gradient(160deg, #14141b 0%, #0b0b10 100%)",
  border: isLight ? "1px solid rgba(0,0,0,0.10)" : "1px solid rgba(255,215,0,0.16)",
  boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
}
```

### 6.11 Linha de lista (chave → valor)

```jsx
{
  display: "flex", justifyContent: "space-between", alignItems: "baseline",
  gap: 10, padding: "7px 0",
  borderTop: isLight ? "1px solid rgba(0,0,0,0.06)" : "1px solid rgba(255,255,255,0.06)",
}
// label: fontSize 13, fontWeight 600
// valor: fontSize 13, fontWeight 700, color: gold
```

---

## 7. Arquitetura de tema

Um contexto simples com persistência em `localStorage` e atributo no `<html>`:

```tsx
type Theme = "dark" | "light";

// no provider:
useEffect(() => {
  localStorage.setItem("app-theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
}, [theme]);

// consumo:
const { isLight, toggleTheme } = useTheme();
```

Os tokens globais vivem em CSS custom properties, sobrescritos por
`[data-theme="light"]`; os componentes leem `isLight` para os valores que
precisam ser calculados em JS.

```css
:root {                          /* escuro = padrão */
  --bg-base: #08090E;   --text-primary: #ffffff;
  --text-secondary: #9CA3AF;   --text-muted: #4B5563;
  --border-color: rgba(255,255,255,0.08);
  --gold-primary: #FFC000;
}
[data-theme="light"] {
  --bg-base: #f4f5f7;   --text-primary: #0a0b0e;
  --text-secondary: #4a5060;   --text-muted: #8a909e;
  --border-color: rgba(0,0,0,0.10);
  --gold-primary: #b87800;
}
```

---

## 8. Anti-padrões (erros reais já cometidos neste sistema)

Todos abaixo foram bugs de produção — verifique cada um antes de entregar.

1. **Cor fixa fora de branch de tema.** Qualquer `color: "#fff"` ou
   `background: "linear-gradient(160deg,#14141b…)"` sem `isLight ?` é um bug
   esperando o usuário trocar de tema. Varredura obrigatória:
   ```bash
   grep -rnE 'color: ?"#fff|color: ?"rgba\(255, ?255, ?255' src/ | grep -v isLight
   grep -rnE 'background: ?"(linear-gradient\(160deg, ?#14141b|#191921|#101014)' src/ | grep -v isLight
   ```
2. **Texto branco sobre o gradiente dourado.** ~2:1 de contraste. Use `#08090E`.
3. **Dourado `#FFC000` como texto/ícone no modo claro.** Use `#b87800`.
4. **Constantes de estilo em nível de módulo.** `const CARD = {…}` fora do
   componente não enxerga o tema — transforme em função: `cardStyle(isLight)`.
5. **`colorScheme` fixo em inputs nativos.** `colorScheme: "dark"` num
   `datetime-local` renderiza o calendário escuro sobre página clara.
6. **Header dependente de scroll.** Cor de texto que só considera o estado
   "rolado" some no topo da página no tema oposto.
7. **Componentes de biblioteca (shadcn/ui) com estilo escuro embutido.** O
   `Card` base precisa ler o tema também.
8. **Sombra escura no tema claro.** No claro use `0 1px 6px rgba(0,0,0,0.07)`;
   sombras fortes sujam o layout.

---

## 9. Visualização de dados

Paleta categórica validada para daltonismo (ΔE ≥ 8 em deuteranopia/protanopia,
≥ 15 em visão normal, contraste ≥ 3:1 contra a superfície) — **ordem fixa,
nunca cicle as cores**:

| Slot | Escuro | Claro |
|---|---|---|
| 1 | `#3987e5` | `#2a78d6` |
| 2 | `#008300` | `#008300` |
| 3 | `#d55181` | `#e87ba4` |
| 4 | `#c98500` | `#eda100` |
| 5 | `#199e70` | `#1baf7a` |
| 6 | `#d95926` | `#eb6834` |
| 7 | `#9085e9` | `#4a3aa7` |
| 8 | `#e66767` | `#e34948` |

Regras:
- Máximo 8 séries; o excedente agrupa em **"Outros"** (cinza `#6b7280` /
  `#9ca3af`), nunca uma 9ª cor gerada.
- Separação de 2px entre fatias/segmentos, na cor da superfície.
- Identidade **nunca** só por cor: legenda com chip + nome + valor.
- Donut com valor total no centro; tooltip com valor absoluto e percentual.

---

## 10. Checklist de conformidade

- [ ] Montserrat carregada com pesos 300/400/600/700
- [ ] Fundo radial + textura de ruído aplicados no `body`
- [ ] Toda seção aberta por micro-label maiúsculo espaçado
- [ ] CTA principal = pílula dourada 56px com texto escuro maiúsculo espaçado
- [ ] Cards com gradiente (160° escuro / 135° claro), raio 16–18px
- [ ] Nenhuma cor fixa fora de branch de tema (rodar os `grep` da §8)
- [ ] Dourado escurecido para `#b87800` em todo texto/ícone do tema claro
- [ ] Inputs com `colorScheme` acompanhando o tema
- [ ] Status sempre com ícone + rótulo, nunca só cor
- [ ] Transição global de 0.35s para troca de tema
- [ ] Navegação inferior flutuante respeitando `env(safe-area-inset-bottom)`
