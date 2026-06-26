const text = "what happens to the mass ($m$) since I didn't\ngive you a value for it?";
const mathTokenRegex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\(.*?\\\)|(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$))/g;
const parts = text.split(mathTokenRegex);
for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) {
        let html = parts[i];
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\n/g, '<br/>');
        parts[i] = html;
    }
}
console.log(parts.join(''));
