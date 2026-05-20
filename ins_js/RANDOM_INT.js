exports.run = async function () {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let d = C.block_data(data);

    let min = d.readInt32LE(0);
    let max = d.readInt32LE(4);

    let v = min + Math.floor(Math.random() * (max - min + 1));

    C.STD.writeInt32LE(v, C.STD_OFFSET);
    C.STD_OFFSET += 4;

    await C.continue_();
};
