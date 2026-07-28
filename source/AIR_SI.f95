function AIR_SI(temp_c, itable)
  implicit none

  real, intent(in) :: temp_c
  integer, intent(in) :: itable
  real :: AIR_SI
  real :: t_k, mu, rho, nu, k_air, pr_air

  real, parameter :: p_ref = 101325.0        ! Pa
  real, parameter :: r_air = 287.05           ! J/(kg*K)
  real, parameter :: g = 9.80665              ! m/s^2
  real, parameter :: mu0 = 1.716e-5           ! Pa*s at T0
  real, parameter :: t0 = 273.15              ! K
  real, parameter :: suth = 111.0             ! K

  ! Use physically meaningful bounds to avoid divide-by-zero and NaNs.
  t_k = max(150.0, min(2500.0, temp_c + 273.15))

  ! Dynamic viscosity from Sutherland's law.
  mu = mu0 * (t_k / t0)**1.5 * (t0 + suth) / (t_k + suth)
  rho = p_ref / (r_air * t_k)
  nu = mu / rho

  ! Conductivity approximation suitable for dry air over SES ranges.
  k_air = 0.0241 * (t_k / 273.15)**0.9
  pr_air = 0.71

  select case (itable)
  case (1)
    AIR_SI = nu
  case (2)
    AIR_SI = k_air
  case (3)
    AIR_SI = pr_air
  case (4)
    AIR_SI = g / (t_k * nu * nu)
  case default
    AIR_SI = nu
  end select

end function AIR_SI
