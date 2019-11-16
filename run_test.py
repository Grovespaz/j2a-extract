
from __future__ import print_function
import os
import sys
import struct
import itertools
import zlib
from types import FunctionType

from j2a import J2A

if sys.version_info[0] <= 2:
    input = raw_input


def _read_hdr():
    global anims, anims_path
    if "anims" in globals():
        return anims
    else:
        print("Reading animations file", anims_path)
        return J2A(anims_path).read()

def show_frame(set_num, anim_num, frame_num):
    try:
        import matplotlib.pyplot as plt
        def show_img(img):
            plt.imshow(img)
            plt.axis('off')
            plt.show()
    except ImportError:
        def show_img(img):
            img.show()

    anims = _read_hdr()
    try:
        frame = anims.sets[set_num].animations[anim_num].frames[frame_num]
    except IndexError:
        print("Error: some index was out of bounds")
        return 1

    rendered = anims.render_pixelmap(frame)
    show_img(rendered)

def show_anim(set_num, anim_num):
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.animation import ArtistAnimation

    anims = _read_hdr()
    s = anims.sets[set_num]
    anim = s.animations[anim_num]

    images = [anims.render_pixelmap(frame) for frame in anim.frames]
    fps = anim.fps

#     borders = np.array([[finfo["hotspotx"], finfo["width"], finfo["hotspoty"], finfo["height"]] for finfo in frameinfo_l])
    borders = np.array([[frame.origin[0], frame.shape[0], frame.origin[1], frame.shape[1]] for frame in anim.frames])
    borders[:,1] += borders[:,0]
    borders[:,3] += borders[:,2]
    extremes = ((borders[:,0].min(), borders[:,1].max()), (borders[:,2].min(), borders[:,3].max()))

    fig, ax = plt.subplots()
    artists = [[plt.imshow(image, animated=True, extent=borders[i])] for i,image in enumerate(images)]
    ani = ArtistAnimation(fig, artists, interval=1000.0/fps, blit=True)
    ax.axis("off")
    ax.set_xlim(extremes[0])
    ax.set_ylim(extremes[1])
    plt.show()

def print_j2a_stats():
    anims = _read_hdr()
    print("Jazz Jackrabbit 2 animations file")
    print("\tsetcount: {}".format(len(anims.sets)))
    for i,s in enumerate(anims.sets):
        print("\tSet {}:".format(i))
        print("\t\tanimcount: {}".format(len(s.animations)))
        print("\t\tsamplecount: {}".format(s._samplecount))
        print("\t\tframecount: {}".format(sum(len(a.frames) for a in s.animations)))

def generate_compmethod_stats(filename, starting_set=0):
    l_level = list(range(1, 10))
    l_method = [zlib.DEFLATED]
    l_wbits = [15]
    l_memLevel = list(range(1, 10))
    l_strategy = list(range(0, 4))  # 4 (= Z_FIXED) causes SEGFAULT sometimes

    anims = _read_hdr()
    struct = generate_compmethod_stats.struct

    def dump(f, raw, setnum, chknum, level, method, wbits, memLevel, strategy):
        print(setnum, chknum, pargs)
        cobj = zlib.compressobj(*pargs)
        length = len(cobj.compress(raw)) + len(cobj.flush())
        f.write(struct.pack(setnum, chknum, level, method, wbits, memLevel, strategy, length))

    with open(filename, "wb") as f:
        for setnum, s in enumerate(anims.sets):
            if setnum < starting_set:
                continue
            print("Dumping for set", setnum)
            for chknum, chk in enumerate(s._chunks):
                raw = zlib.decompress(chk[0], zlib.MAX_WBITS, chk[1])
                [dump(f, raw, setnum, chknum, level, method, wbits, memLevel, strategy)
                    for level    in l_level
                    for method   in l_method
                    for wbits    in l_wbits
                    for memLevel in l_memLevel
                    for strategy in l_strategy
                ]
generate_compmethod_stats.struct = struct.Struct("<BBBBBBBL")

def stress_test():
    anims = _read_hdr()
    for s in anims.sets:
        for anim in s.animations:
            for frame in anim.frames:
                anims.render_pixelmap(frame)

def writing_test():
    import io
    anims = _read_hdr()
    anims.unpack()
    my_out = io.BytesIO()
    my_out.close = lambda : None
    def open_mock(filename, mode):
        assert(filename == "TEST" and mode in ("rb", "wb"))
        my_out.seek(0)
        return my_out
    if sys.version_info[0] <= 2:
        __builtins__.open = open_mock
    else:
        import builtins
        builtins.open = open_mock
    anims.write("TEST")
    anims2 = J2A("TEST").read().unpack()

def unpacking_test():
    anims = _read_hdr()
    anims.unpack()

def packing_test():
    anims = _read_hdr()
    pristine_chunks = [s._chunks for s in anims.sets]
    anims.unpack().pack()
#     pristine_chunks[-1][2] = (zlib.compress(b'\x00'), 0)
    new_chunks = [s._chunks for s in anims.sets]
    failed = False
    for i, (pset, nset) in enumerate(zip(pristine_chunks, new_chunks)):
        for chunk_num, pchunk, nchunk in zip(range(4), pset, nset):
            if zlib.decompress(pchunk[0], zlib.MAX_WBITS, pchunk[1]) != zlib.decompress(nchunk[0], zlib.MAX_WBITS, nchunk[1]):
                print("Difference in set %d, chunk %d" % (i, chunk_num))
                failed = True
    print("Packing test", "FAILED" if failed else "PASSED")

def _random_pixmap(seed=None, width=260, height=80):
    import numpy as np
    import random
    random.seed(seed)
    def gen(func, limit):
        csum = 0
        while True:
            val = func()
            csum += val
            if csum < limit:
                yield val
            else:
                yield val - csum + limit
                break
    a0 = b''.join(b * times for times, b in zip(gen(lambda : random.randrange(255), width * height), itertools.cycle([b'\x00', b'\xff'])))
    assert(len(a0) == width * height)
    return np.frombuffer(a0, dtype=np.uint8).reshape((height, width))

def frame_encoding_test(seed=None):
    a = _random_pixmap()
    frame = J2A.Frame(shape = a.shape[::-1], pixmap = a)
    frame.encode_image()

def mask_autogen_test(times = 1):
    from random import randint
    def bit_iter(a):
        for elt in a:
            for _ in range(8):
                yield elt & 1
                elt >>= 1
    try:
        for _ in range(times):
            width, height = randint(1, 50), randint(1, 50)
            pixmap = _random_pixmap(None, width, height)
#             pixmap = [[max(0, randint(-128, 127)) for _ in range(width)] for _ in range(height)]
            frame = J2A.Frame(shape = (width, height), pixmap = pixmap)
            frame.autogenerate_mask()
            mask = bytearray(frame.mask)
            for bit, pix in zip(bit_iter(mask), itertools.chain(*pixmap)):
                assert(bit == bool(pix))
            assert(mask[-1] >> (1 + ((width*height - 1) & 7)) == 0)
    except AssertionError as e:
        print(width, height)
        print(pixmap)
        print(mask.hex())
        raise

def profile_func(funcname, arg, *pargs):
    '''
    Call function repeatedly according to the condition specified by `arg`.
    `funcname` specifies the name of the function in the global namespace to call.
    `arg` must be a string of one of the following types:
     - "#x", where # is an integer; this calls the function # times
     - "#s", where # is an integer; this calls the function for at least # seconds
    The function is called with `*pargs` positional arguments.
    This function is useful for profiling from the command line with a command such as:
    > python -m cProfile run_test.py profile_stress_test <arg>
    Optionally you can add `-o <file>` after "cProfile" to save the results to a file.
    Afterwards, to view it use:
    > python -m pstats <file>
    '''
    from time import time
    global fmap
    f = fmap[funcname]
    startingtime = time()
    if arg[-1] == "x":
        arg = int(arg[:-1])
        condition = lambda i,t : i < arg
    elif arg[-1] == "s":
        arg = float(arg[:-1])
        condition = lambda i,t : t <= arg
    else:
        raise KeyError

    curtime = startingtime
    for i in itertools.count():
        if condition(i, curtime-startingtime):
            f(*pargs)
            curtime = time()
        else:
            print("Running for {:.3} s, {} iterations".format(curtime-startingtime, i))
            return

#############################################################################################################

if __name__ == "__main__":
    fmap = {k: v for k,v in globals().items() if isinstance(v, FunctionType) and not k.startswith('_')}

    assert(int(True) is 1)
    isint = lambda x : x[int(x[:1] in '+-'):].isdigit()

    anims_path = None
    fargs = []
    for arg in sys.argv[2:]:
        if arg.endswith('.j2a'):
            anims_path = arg
        else:
            if isint(arg): # Don't use integers for file names
                arg = int(arg)
            fargs.append(arg)
    anims_path = anims_path or os.path.join(os.path.dirname(sys.argv[0]), "Anims.j2a")

    print("Calling {} with arguments: {}".format(sys.argv[1], fargs))
    retval = fmap[sys.argv[1]](*fargs)
    if isinstance(retval, int):
        sys.exit(retval)
