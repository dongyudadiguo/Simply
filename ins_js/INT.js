exports.run = async function () {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let v = C.block_data(data).readInt32LE(0);

    C.STD.writeInt32LE(v, C.STD_OFFSET);
    C.STD_OFFSET += 4;

    await C.continue_();
};
