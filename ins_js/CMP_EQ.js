exports.run = async function () {
    const C = CVM;

    let a = C.STD.readInt32LE(0);
    let b = C.STD.readInt32LE(4);

    C.STD[0] = a === b ? 1 : 0;
    C.STD_OFFSET = 1;

    await C.continue_();
};
