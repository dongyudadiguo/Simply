(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let id = C.block_data(data).toString("hex");

    let v = Buffer.alloc(C.VAR_SIZE);

    C.STD.copy(v, 0, 0, C.VAR_SIZE);

    C.VARS.set(id, v);

    await C.continue_();
})();
