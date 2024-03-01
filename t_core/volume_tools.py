# %%
from typing import Callable, Union, Iterable, Tuple
from pathlib import Path
import numpy as np
import scipy.io as sio
import torch
import matplotlib.pyplot as plt
import cv2 as cv
from statsmodels.tsa.stattools import acf
# %%
def displace_rigid_xyz(vol: np.ndarray, disp: Iterable[int]) -> np.ndarray:
    """Deform by rigid body displacement

    Image wil be padded by the minimum value of the volume.
    Args:
        vol (np.ndarray): input volume
        disp (Iterable[int]): number of voxels to displace in x, y, z

    Returns:
        np.ndarray: output volume
    """
    new_vol = vol.min()*np.ones_like(vol)
    new_vol[disp[0]:, disp[1]:, disp[2]:] = vol[:-disp[0],:-disp[1],:-disp[2]]
    return new_vol

def deform_general(vol_a: np.ndarray, x_func: Callable, y_func: Callable, z_func: Callable) -> np.ndarray:
    """Deform volume based on 3D coordinate transformation functions.

    Note that torch grid_sample takes in grid coordinates from which to sample.
    Therefore, we need to provide the inverse transformation functions -
    i.e. we provide volume A and functions that map coordinates
    from new volume B to old volume A.
    Args:
        vol_a (np.ndarray): 3d volume
        x_func (Callable): x-function with signature (x_b,y_b,z_b) -> X_a
        y_func (Callable): y-function with signature (x_b,y_b,z_b) -> Y_a
        z_func (Callable): z-function with signature (x_b,y_b,z_b) -> Z_a

    Returns:
        vol_b (np.ndarray): deformed volume
    """
    res = vol_a.shape
    vol_torch = torch.from_numpy(vol_a).view(1,1,*res)
    x = torch.linspace(-1, 1, res[0])
    y = torch.linspace(-1, 1, res[1]) 
    z = torch.linspace(-1, 1, res[2]) 
    X,Y,Z = torch.meshgrid(x,y,z, indexing='ij')
    X1 = x_func(X,Y,Z)
    Y1 = y_func(X,Y,Z)
    Z1 = z_func(X,Y,Z)
    grid = torch.stack((Z1,Y1,X1), dim=-1).unsqueeze(0) # pytorch uses order z,y,x
    deformed_volume = torch.nn.functional.grid_sample(vol_torch, grid, align_corners=True)
    vol_b = deformed_volume.squeeze().numpy()
    return vol_b

def plot_undef_def_slices(vol: np.ndarray, def_vol: np.ndarray):
    """Plot slices of undeformed and deformed volumes.

    Args:
        vol (np.ndarray): undeformed volume
        def_vol (np.ndarray): deformed volume
    """
    fig, ax = plt.subplots(3,3)
    
    # Row 0 - undeformed
    res = vol.shape
    ax[0,0].imshow(vol[:, :, res[2]//2])
    ax[0,0].set_title('z-slice')
    ax[0,0].set_ylabel('x')
    ax[0,0].set_xlabel('y')
    ax[0,1].imshow(vol[res[0]//2,:,:])
    ax[0,1].set_title('x-slice')
    ax[0,1].set_ylabel('y')
    ax[0,1].set_xlabel('z')
    ax[0,2].imshow(vol[:,res[1]//2,:])
    ax[0,2].set_title('y-slice')
    ax[0,2].set_ylabel('x')
    ax[0,2].set_xlabel('z')

    # Row 1 - deformed
    ax[1,0].imshow(def_vol[:, :, res[2]//2])
    ax[1,0].set_title('z-slice (deformed)')
    ax[1,0].set_ylabel('x')
    ax[1,0].set_xlabel('y')
    ax[1,1].imshow(def_vol[res[0]//2,:,:])
    ax[1,1].set_title('x-slice (deformed)')
    ax[1,1].set_ylabel('y')
    ax[1,1].set_xlabel('z')
    ax[1,2].imshow(def_vol[:,res[1]//2,:])
    ax[1,2].set_title('y-slice (deformed)')
    ax[1,2].set_ylabel('x')
    ax[1,2].set_xlabel('z')

    # Row 2 - difference
    ax[2,0].imshow(def_vol[:, :, res[2]//2] - vol[:, :, res[2]//2])
    ax[2,0].set_title('z-slice (difference)')
    ax[2,0].set_ylabel('x')
    ax[2,0].set_xlabel('y')
    ax[2,1].imshow(def_vol[res[0]//2,:,:] - vol[res[0]//2,:,:])
    ax[2,1].set_title('x-slice (difference)')
    ax[2,1].set_ylabel('y')
    ax[2,1].set_xlabel('z')
    ax[2,2].imshow(def_vol[:,res[1]//2,:] - vol[:,res[1]//2,:])
    ax[2,2].set_title('y-slice (difference)')
    ax[2,2].set_ylabel('x')
    ax[2,2].set_xlabel('z')

    plt.tight_layout()
    plt.show()

def plot_volume(vol: np.ndarray):
    fig, ax = plt.subplots(1,3)
    ax[0].imshow(vol[vol.shape[0]//2, :, :])
    ax[0].set_ylabel('y')
    ax[0].set_xlabel('z')
    ax[1].imshow(vol[:, vol.shape[1]//2, :])
    ax[1].set_ylabel('x')
    ax[1].set_xlabel('z')
    ax[2].imshow(vol[:, :, vol.shape[2]//2])
    ax[2].set_ylabel('x')
    ax[2].set_xlabel('y')
    fig.tight_layout()
    plt.show()

def load_volume(fn: Union[str, Path], resolution: Iterable[int]) -> np.ndarray:
    """Load volume data from binary file.

    By convention, the order of the input dimensions (e.g. in VG Studio) 
    is (z,y,x). We return volume with order (x,y,z)
    Args:
        fn (Union[str, Path]): file name
        resolution (Iterable[int]): [x,y,z] resolution in voxels

    Returns:
        np.ndarray: volume with ndim=3 and shape (x,y,z)
    """
    if isinstance(fn, str):
        fn = Path(fn)
    assert fn.exists()
    data = np.fromfile(fn, dtype=np.float32)
    vol = data.reshape([resolution[i] for i in [2,1,0]])
    vol = vol.swapaxes(0,2)
    return vol

def save_volume(fn: Path, vol: np.ndarray):
    """Save volume to binary file.

    We save the volume with order of dimensions (z,y,x).
    Args:
        fn (Path): output file path
        vol (np.ndarray): 3d volume with order of dimensions (x,y,z)
    """
    vol.swapaxes(0,2).flatten().tofile(fn)

def make_volume(size: Tuple[int,int,int], speckle_size: int = 10, convolution_kernel: int = 1) -> np.ndarray:
    """Create synthetic volume with background, material, and texture.

    Args:
        size (Tuple[int,int,int]): desired resolution in voxels. 
            The final resolution might be different due to modulo operation.
        speckle_size (int, optional): size of intermediate voxels. 
            Defaults to 10.
        convolution_kernel (int, optional): length-scale of Gaussian blur. 
            Only active if greater than 1. Must be odd. Defaults to 1.

    Returns:
        np.ndarray: 3d volume
    """
    reduced_size = (size[0]//speckle_size, size[1]//speckle_size, size[2]//speckle_size)
    vol = np.zeros(reduced_size, dtype=np.float32)
    # material and air
    padding_ratio = 0.15
    pad = int(np.min(reduced_size) * padding_ratio) 
    vol[pad:-pad,pad:-pad,pad:-pad] = 1
    # noise on top
    vol += 0.1 * np.random.randn(*reduced_size)
    torch_vol = torch.from_numpy(vol).view(1,1,*reduced_size)
    vol = torch.nn.functional.interpolate(torch_vol, 
        scale_factor=speckle_size, mode='nearest'
        )
    if convolution_kernel > 1:
        k = convolution_kernel
        assert k % 2 == 1
        x = torch.linspace(-1, 1, k)
        ker = torch.exp(-x**2/0.5)
        ker_3d = ker[:,None,None] * ker[None,:,None] * ker[None,None,:]
        ker_3d /= ker_3d.sum()
        vol = torch.nn.functional.conv3d(vol,
            ker_3d[None,None,...],
            padding=k//2
            )
    vol = vol.squeeze().numpy()
    return vol

def plot_acf(vol: np.ndarray, **fig_kwargs):
    """Plot volume characteristics including autocorrelation function.

    Args:
        vol (np.ndarray): input 3d volume
    """
    resolution = vol.shape
    im = vol[resolution[0]//2]
    fig, ax = plt.subplots(nrows=2, ncols=3, gridspec_kw={'height_ratios':[3,2]}, **fig_kwargs)
    ax[0,0].xaxis.tick_top()
    ax[0,0].xaxis.set_label_position('top')
    ax[0,0].imshow(im.T, cmap='gray')
    ax[0,0].set_xlabel('y')
    ax[0,0].set_ylabel('z')
    pad = int(np.min(resolution) * 0.17)
    ylims = (pad,resolution[1]-pad)
    zlims = (pad,resolution[2]-pad)
    zoomed = im[ylims[0]:ylims[1], zlims[0]:zlims[1]]
    ax[0,1].xaxis.tick_top()
    ax[0,1].xaxis.set_label_position('top')
    ax[0,1].imshow(im.T, cmap='gray', clim=(zoomed.min(), zoomed.max()))
    ax[0,1].set_xlim(ylims)
    ax[0,1].set_ylim(zlims)
    ax[0,1].set_xlabel('y')
    ax[0,1].set_ylabel('z')
    ax[0,0].indicate_inset_zoom(ax[0,1], edgecolor='black')
    ax[0,2].hist(im.ravel(), bins=50, lw=1, edgecolor='k', facecolor='none')
    ax[0,2].set_xlabel('Grey value')
    ax[0,2].set_yscale('log')
    ax[0,2].set_box_aspect(1)

    ax[1,0].plot(im[resolution[1]//2])
    ax[1,0].set_xlabel('z')
    ax[1,0].set_ylabel('Grey value')
    ax[0,0].axvline(resolution[1]//2, color='r', ls='--')
    ax[1,0].annotate('',
                    xy=(0.5, -0.05), xycoords=ax[0,0].transAxes,
                    xytext=(0.5,1.0),
                    textcoords=ax[1,0].transAxes,
                    ha="center", va="top",
                    arrowprops=dict(arrowstyle="->", color='r'),
                    )
    ax[1,1].set_xlabel('z')
    ax[1,1].set_ylabel('Grey value')
    ax[1,1].set_xlim(zlims)
    ax[1,1].set_ylim((zoomed.min(), zoomed.max()))
    for i,p in enumerate([0.25, 0.5, 0.75]):
        ax[1,1].plot(im[ylims[0]+int(zoomed.shape[0]*p)], alpha=0.5, marker='.')
        ax[0,1].axvline(ylims[0]+int(zoomed.shape[0]*p), color=f'C{i}', ls='--')
        ax[1,1].annotate('',
                    xy=(p, -0.05), xycoords=ax[0,1].transAxes,
                    xytext=(p,1.0),
                    textcoords=ax[1,1].transAxes,
                    ha="center", va="top",
                    arrowprops=dict(arrowstyle="->", color=f'C{i}'),
                    )

        x = zoomed[int(zoomed.shape[0]*p)]
        ax[1,2].plot(acf(x, nlags=25), marker='o', markersize=5, alpha=0.75)
    ax[1,2].set_xlabel('Lag')
    ax[1,2].set_ylabel('ACF')
    ax[1,2].axhline(0, color='k', lw=0.5)
    fig.tight_layout()
    plt.show()

def select_pos_in_volume(_vol: np.ndarray) -> Tuple[int,int,int]:
    """Take slices through the volume and select a position.

    Args:
        vol (np.ndarray): 3d volume

    Returns:
        Tuple[int,int,int]: voxel coordinates of selected position
    """
    cv.namedWindow('3D Volume', cv.WINDOW_NORMAL)
    cmin, cmax = _vol.min(), _vol.max()
    vol = (_vol - cmin) / (cmax - cmin)
    
    def on_slider_change(z):
        cv.imshow('3D Volume', vol[:,:,z])

    c_x, c_y, c_z = 0, 0, 0
    def on_mouse_click(event, x, y, flags, param):
        nonlocal c_x, c_y, c_z
        if event == cv.EVENT_LBUTTONDOWN:
            c_x, c_y, c_z = x, y, cv.getTrackbarPos('z', '3D Volume')
            print(f'x: {c_x}, y: {c_y}, z: {c_z}')

    cv.createTrackbar('z', '3D Volume', 0, vol.shape[2]-1, on_slider_change)
    on_slider_change(0)
    cv.setMouseCallback('3D Volume', on_mouse_click)

    cv.waitKey()
    cv.destroyAllWindows()
    return c_x, c_y, c_z

class GaussianDeformationField:
    """Localised Gaussian deformation field.
    """
    def __init__(self, sigma_xyz: Iterable[float], A_xyz: Iterable[float], r0_xyz: Iterable[float] = (0,0,0)):
        """Create a Gaussian deformation field.

        Depending on the values of sigma_xyz and A_xyz, the field can be
        localised to an ellipsoidal region {sigma_x, sigma_y, sigma_z}>0,
        cylindrical region (e.g. {sigma_x, sigma_y}>0, sigma_z=0), or 
        planar region (e.g. {sigma_x, sigma_y}=0, sigma_z>0).
        Args:
            sigma_xyz (Iterable[float]): Length-scales of field in x, y, z
                Any zero value will result in effectively infinite length-scale
            A_xyz (Iterable[float]): Magnitude of field in x, y, z.
            r0_xyz (Iterable[float], optional): Spatial centering of the Gaussian.
                Volume bounds are (-1,1) in all dimensions. Defaults to (0,0,0).
        """
        self.sigma_xyz = sigma_xyz
        self.A_xyz = A_xyz
        self.r0_xyz = r0_xyz
        for s,a in zip(sigma_xyz, A_xyz):
            assert s >= 0
            if s>0:
                assert a < s*np.exp(-0.5)
        # note for this type of field, the requirement for compatibility is
        # A_vox < sigma_vox*exp(-0.5) ~ 1.65*sigma_vox
                
    def gaussian_magnitude(self, x: torch.Tensor, y: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        magnitude = 1.0
        for s, x_i, r_i in zip(self.sigma_xyz, [x,y,z], self.r0_xyz):
            if s > 0:
                if isinstance(magnitude, float):
                    magnitude = torch.exp(-0.5*((x_i - r_i)**2/s**2))
                else:
                    magnitude *= torch.exp(-0.5*((x_i - r_i)**2/s**2))
        return magnitude
    
    def x_func(self, x: torch.Tensor, y: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        if self.A_xyz[0] == 0:
            return x
        return x + self.A_xyz[0]*self.gaussian_magnitude(x,y,z)
        
    def y_func(self, x: torch.Tensor, y: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        if self.A_xyz[1] == 0:
            return y
        return y + self.A_xyz[1]*self.gaussian_magnitude(x,y,z)
    
    def z_func(self, x: torch.Tensor, y: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        if self.A_xyz[2] == 0:
            return z
        return z + self.A_xyz[2]*self.gaussian_magnitude(x,y,z)
    
    def __call__(self, vol: np.ndarray) -> np.ndarray:
        """Apply the deformation field to volume.

        Args:
            vol (np.ndarray): 3d volume

        Returns:
            np.ndarray: deformed volume
        """
        return deform_general(
            vol, 
            self.x_func,
            self.y_func,
            self.z_func
        )