exports.run = async function () {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let id = C.block_data(data).toString("hex");

    let v = C.VARS.get(id);

    if (!v)
        v = Buffer.alloc(C.VAR_SIZE);

    v.copy(C.STD, C.STD_OFFSET, 0, C.VAR_SIZE);

    C.STD_OFFSET += C.VAR_SIZE;

    await C.continue_();
};
