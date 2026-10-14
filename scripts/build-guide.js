const fs = require('fs');
const path = require('path');
const MarkdownIt = require('markdown-it');
const mdAnchor = require('markdown-it-anchor');
const { chromium } = require('@playwright/test');

async function build() {
  const guideDir = path.join(__dirname, '..', 'docs', 'guia-usuario');
  const mdFiles = fs.readdirSync(guideDir)
    .filter(f => f.match(/^\d+-.*\.md$/))
    .sort();

  const md = new MarkdownIt({ html: true, linkify: true });
  md.use(mdAnchor);

  let htmlContent = '';
  for (const file of mdFiles) {
    const raw = fs.readFileSync(path.join(guideDir, file), 'utf-8').replace(/^\uFEFF/, '');
    htmlContent += md.render(raw);
    htmlContent += '\n<div class="page-break"></div>\n';
  }

  const cssPath = path.join(guideDir, 'assets', 'css', 'guide.css');
  const css = fs.readFileSync(cssPath, 'utf-8');

  const html = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Guía de usuario — ContaFis</title>
<style>${css}</style>
</head>
<body>
${htmlContent}
</body>
</html>`;

  const tmpHtml = path.join(guideDir, '_build.html');
  fs.writeFileSync(tmpHtml, html);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + tmpHtml, { waitUntil: 'load' });
  await page.pdf({
    path: path.join(guideDir, 'guia-usuario.pdf'),
    format: 'A4',
    printBackground: true,
    margin: { top: '2cm', bottom: '2cm', left: '1.8cm', right: '1.8cm' },
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: '<div style="font-size:9px;width:100%;text-align:center;color:#888;">Página <span class="pageNumber"></span> de <span class="totalPages"></span></div>',
  });
  await browser.close();

  fs.unlinkSync(tmpHtml);
  console.log('✓ PDF generado: docs/guia-usuario/guia-usuario.pdf');
}

build().catch(err => { console.error(err); process.exit(1); });
