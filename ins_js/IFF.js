exports.run = async function () {
    const C = CVM;

    let data = C.next_of(C.PTR);

    let trueblock = {
        buf: data.buf,
        off: data.off + 4
    };

    let falseblock = C.next_of(trueblock);

    let after = C.next_of(data);
    after = C.skip_data_of(after);

    C.FRAMES.push(after);

    if (C.STD[0])
        await C.run_block_auto(trueblock);
    else
        await C.run_block_auto(falseblock);
};
