/**
 * HTML to PDF with Puppeteer (MathJax, tables 지원)
 * 사용: node scripts/html_to_pdf.js
 */
const puppeteer = require('puppeteer');
const path = require('path');
const { pathToFileURL } = require('url');

const baseDir = path.join(__dirname, '..');
const htmlPath = process.argv[2] || path.join(baseDir, 'report_temp.html');
const pdfPath = htmlPath.replace(/\.html$/i, '.pdf');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  await page.goto(pathToFileURL(htmlPath).href, {
    waitUntil: 'networkidle0',
    timeout: 30000
  });
  
  // MathJax 렌더링 대기
  await page.evaluate(() => {
    return new Promise((resolve) => {
      if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise().then(resolve).catch(() => resolve());
      } else {
        setTimeout(resolve, 3000);
      }
    });
  });
  
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    margin: { top: '20mm', right: '20mm', bottom: '20mm', left: '20mm' },
    printBackground: true
  });
  
  await browser.close();
  console.log('Saved:', pdfPath);
})();
