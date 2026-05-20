(async () => {
    const readline = require("readline/promises");
    const C = CVM;

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    let s = await rl.question("> ");

    rl.close();

    let v = parseInt(s, 10);

    if (Number.isNaN(v))
        v = 0;

    C.STD.writeInt32LE(v, C.STD_OFFSET);
    C.STD_OFFSET += 4;

    await C.continue_();
})();
