exports.run = async function () {
    CVM.STD.fill(0);
    CVM.STD_OFFSET = 0;
    await CVM.continue_();
};
