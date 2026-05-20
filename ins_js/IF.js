exports.run = async function () {
    const C = CVM;

    let data = C.next_of(C.PTR);

    let trueblock = {
        buf: data.buf,
        off: data.off + 4
    };

    let after = C.next_of(data);
    after = C.skip_data_of(after);

    if (C.STD[0]) {
        C.FRAMES.push(after);
        await C.run_block_auto(trueblock);
    } else {
        C.PTR = after;
        await C.run_block_auto(C.PTR);
    }
};
