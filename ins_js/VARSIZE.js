(async () => {
    let data = CVM.next_of(CVM.PTR);
    CVM.VAR_SIZE = CVM.block_size(data);
    await CVM.continue_();
})();
